from odoo import api, fields, models, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduDepositAdjustment(models.Model):
    """
    Deposit adjustment — an approved deduction from a student's
    security deposit balance.

    Examples:
      * deduction to cover damage costs
      * transfer of deposit toward semester fees
      * partial forfeiture due to policy violation

    On approval, a journal entry is created:
      Debit : Deposit Liability account
      Credit: Destination account (revenue / expense)
    """

    _name = 'edu.deposit.adjustment'
    _description = 'Deposit Adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # ── Reference ─────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        index=True,
    )
    ledger_id = fields.Many2one(
        'edu.deposit.ledger',
        string='Deposit Ledger',
        required=True,
        ondelete='cascade',
        index=True,
    )
    student_id = fields.Many2one(
        related='ledger_id.student_id',
        string='Student',
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related='ledger_id.partner_id',
        string='Contact',
        store=True,
    )

    # ── Adjustment Details ────────────────────────────────────────────────
    amount = fields.Monetary(
        string='Adjustment Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        tracking=True,
    )
    reference = fields.Char(
        string='External Reference',
        tracking=True,
        help='Incident number, damage report, policy reference, etc.',
    )
    date = fields.Date(
        string='Adjustment Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    # ── Accounting ────────────────────────────────────────────────────────
    deposit_account_id = fields.Many2one(
        'account.account',
        string='Deposit Liability Account',
        help='Debit account (deposit liability being reduced).',
    )
    destination_account_id = fields.Many2one(
        'account.account',
        string='Destination Account',
        help='Credit account (revenue / expense receiving the amount).',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain="[('type', '=', 'general')]",
    )
    account_move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        ondelete='set null',
        copy=False,
        readonly=True,
    )

    # ── Approval ──────────────────────────────────────────────────────────
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        copy=False,
    )

    # ── State ─────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # ── Convenience ───────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='ledger_id.currency_id',
        string='Currency',
        store=True,
    )
    company_id = fields.Many2one(
        related='ledger_id.company_id',
        string='Company',
        store=True,
    )

    # ── Display name ──────────────────────────────────────────────────────
    @api.depends('name', 'student_id.display_name', 'amount')
    def _compute_display_name(self):
        for rec in self:
            ref = rec.name or 'New'
            student = rec.student_id.display_name or ''
            rec.display_name = f'{ref} — {student}'

    # ── Sequence ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = (
                    seq.next_by_code('edu.deposit.adjustment') or '/'
                )
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if float_compare(rec.amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(
                    'Adjustment amount must be greater than zero.'
                )

    # ── State Transitions ─────────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft adjustments can be submitted.')
        self.write({'state': 'submitted'})

    def action_approve(self):
        """
        Approve the adjustment.  Creates a journal entry to reduce
        the deposit liability.
        """
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(
                    'Only submitted adjustments can be approved.'
                )
            # Validate balance
            ledger = rec.ledger_id
            available = float_round(
                ledger.balance, precision_digits=2
            )
            if float_compare(
                rec.amount, available, precision_digits=2
            ) > 0:
                raise UserError(
                    f'Adjustment amount ({rec.amount}) exceeds '
                    f'available deposit balance ({available}).'
                )

        for rec in self:
            rec._create_adjustment_journal_entry()

        self.write({
            'state': 'approved',
            'approved_by': self.env.uid,
            'approved_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        for rec in self:
            if rec.state in ('approved',) and rec.account_move_id:
                if rec.account_move_id.state == 'posted':
                    raise UserError(
                        'Cannot cancel — the journal entry is already '
                        'posted.  Reverse it in Accounting first.'
                    )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    'Only cancelled adjustments can be reset to draft.'
                )
        self.write({
            'state': 'draft',
            'approved_by': False,
            'approved_date': False,
        })

    # ── Journal Entry Creation ────────────────────────────────────────────
    def _create_adjustment_journal_entry(self):
        """
        Create a journal entry for the deposit adjustment:
          Debit : Deposit Liability account
          Credit: Destination account (revenue/expense)
        """
        self.ensure_one()
        if not self.deposit_account_id or not self.destination_account_id:
            # Try to auto-detect from deposit fee heads
            deposit_heads = self.env['edu.fee.head'].search([
                ('fee_nature', '=', 'deposit'),
                ('liability_account_id', '!=', False),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if deposit_heads and not self.deposit_account_id:
                self.deposit_account_id = deposit_heads.liability_account_id
            if not self.deposit_account_id or not self.destination_account_id:
                # Skip journal entry if accounts not configured
                self.message_post(
                    body=(
                        '<em>Journal entry skipped — deposit or '
                        'destination account not configured.</em>'
                    ),
                    message_type='notification',
                )
                return

        journal = self.journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', '=', 'general'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not journal:
            self.message_post(
                body='<em>Journal entry skipped — no general journal.</em>',
                message_type='notification',
            )
            return

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': f'Deposit Adjustment {self.name}',
            'company_id': self.company_id.id,
            'line_ids': [
                Command.create({
                    'name': f'Deposit adjustment: {self.reason[:80]}',
                    'account_id': self.deposit_account_id.id,
                    'partner_id': self.partner_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                }),
                Command.create({
                    'name': f'Deposit adjustment: {self.reason[:80]}',
                    'account_id': self.destination_account_id.id,
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'currency_id': self.currency_id.id,
                }),
            ],
        })
        self.account_move_id = move.id
