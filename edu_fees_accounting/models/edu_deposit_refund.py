from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduDepositRefund(models.Model):
    """
    Deposit refund — an approved outbound payment returning part or
    all of a student's security deposit.

    On completion (``action_process``), an outbound ``account.payment``
    is created to send money back to the student.

    Lifecycle:
        draft → submitted → approved → done
                                        ↳ (cancelled at any stage
                                            before done)
    """

    _name = 'edu.deposit.refund'
    _description = 'Deposit Refund'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'refund_date desc, id desc'
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

    # ── Refund Details ────────────────────────────────────────────────────
    amount = fields.Monetary(
        string='Refund Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    payment_method = fields.Selection(
        selection=[
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('cash', 'Cash'),
            ('online', 'Online Transfer'),
            ('other', 'Other'),
        ],
        string='Payment Method',
        default='bank_transfer',
        required=True,
        tracking=True,
    )
    refund_date = fields.Date(
        string='Refund Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    notes = fields.Text(
        string='Notes',
        tracking=True,
    )

    # ── Accounting ────────────────────────────────────────────────────────
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain="[('type', 'in', ('bank', 'cash'))]",
        tracking=True,
    )
    deposit_account_id = fields.Many2one(
        'account.account',
        string='Deposit Liability Account',
        help='Account to debit (reduce deposit liability).',
    )
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Accounting Payment',
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
    processed_by = fields.Many2one(
        'res.users',
        string='Processed By',
        readonly=True,
        copy=False,
    )
    processed_date = fields.Datetime(
        string='Processed Date',
        readonly=True,
        copy=False,
    )

    # ── State ─────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('done', 'Done'),
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
                    seq.next_by_code('edu.deposit.refund') or '/'
                )
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if float_compare(rec.amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(
                    'Refund amount must be greater than zero.'
                )

    # ── State Transitions ─────────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft refunds can be submitted.')
        self.write({'state': 'submitted'})

    def action_approve(self):
        """Approve the refund request.  Validates balance."""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(
                    'Only submitted refunds can be approved.'
                )
            ledger = rec.ledger_id
            available = float_round(ledger.balance, precision_digits=2)
            if float_compare(
                rec.amount, available, precision_digits=2
            ) > 0:
                raise UserError(
                    f'Refund amount ({rec.amount}) exceeds available '
                    f'deposit balance ({available}).'
                )
        self.write({
            'state': 'approved',
            'approved_by': self.env.uid,
            'approved_date': fields.Datetime.now(),
        })

    def action_process(self):
        """
        Process the refund — create an outbound ``account.payment``
        to return money to the student.
        """
        for rec in self:
            if rec.state != 'approved':
                raise UserError(
                    'Only approved refunds can be processed.'
                )
            rec._create_refund_payment()

        self.write({
            'state': 'done',
            'processed_by': self.env.uid,
            'processed_date': fields.Datetime.now(),
        })

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(
                    'Cannot cancel a completed refund. '
                    'Reverse the payment in Accounting instead.'
                )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    'Only cancelled refunds can be reset to draft.'
                )
        self.write({
            'state': 'draft',
            'approved_by': False,
            'approved_date': False,
        })

    # ── Payment Creation ──────────────────────────────────────────────────
    def _create_refund_payment(self):
        """
        Create an outbound ``account.payment`` that returns deposit
        money to the student.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            raise UserError('No partner on this refund — cannot create payment.')

        journal = self.journal_id
        if not journal:
            jtype = 'cash' if self.payment_method == 'cash' else 'bank'
            journal = self.env['account.journal'].search([
                ('type', '=', jtype),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not journal:
            self.message_post(
                body=(
                    '<em>Payment creation skipped — no suitable '
                    'journal found.  Process manually.</em>'
                ),
                message_type='notification',
            )
            return

        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': self.amount,
            'journal_id': journal.id,
            'date': self.refund_date,
            'ref': f'Deposit Refund {self.name}',
            'currency_id': self.currency_id.id,
        }

        # If deposit account is set, use it as destination account
        if self.deposit_account_id:
            payment_vals['destination_account_id'] = (
                self.deposit_account_id.id
            )

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()
        self.account_payment_id = payment.id

        self.message_post(
            body=(
                f'<strong>Refund payment created:</strong> {payment.name}'
            ),
            message_type='notification',
        )

    # ── Smart Button ──────────────────────────────────────────────────────
    def action_view_payment(self):
        self.ensure_one()
        if not self.account_payment_id:
            raise UserError('No payment linked.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.account_payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
