from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round


class EduDepositLedger(models.Model):
    """
    Student deposit ledger — tracks the lifecycle of refundable
    security deposits for a single student.

    One ledger per student.  Balances are computed from:
      * collected = paid amount on deposit-nature dues
      * adjusted = sum of approved adjustment records
      * refunded = sum of completed refund records
      * balance = collected − adjusted − refunded

    The ledger does NOT hold money — it is a tracking record.
    Actual accounting entries live in ``account.move`` and
    ``account.payment``.
    """

    _name = 'edu.deposit.ledger'
    _description = 'Student Deposit Ledger'
    _inherit = ['mail.thread']
    _order = 'student_id'
    _rec_name = 'display_name'

    # ── Identity ──────────────────────────────────────────────────────────
    student_id = fields.Many2one(
        'edu.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        related='student_id.partner_id',
        string='Contact',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='student_id.company_id',
        string='Company',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency',
        store=True,
    )

    # ── Balances (computed) ───────────────────────────────────────────────
    total_collected = fields.Monetary(
        string='Total Collected',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True,
        help='Sum of paid deposit-nature dues.',
    )
    total_adjusted = fields.Monetary(
        string='Total Adjusted',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True,
        help='Sum of approved deposit adjustments.',
    )
    total_refunded = fields.Monetary(
        string='Total Refunded',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True,
        help='Sum of completed deposit refunds.',
    )
    balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True,
        help='Current deposit balance = collected − adjusted − refunded.',
    )

    # ── Child records ─────────────────────────────────────────────────────
    adjustment_ids = fields.One2many(
        'edu.deposit.adjustment',
        'ledger_id',
        string='Adjustments',
    )
    refund_ids = fields.One2many(
        'edu.deposit.refund',
        'ledger_id',
        string='Refunds',
    )
    adjustment_count = fields.Integer(
        string='Adjustments',
        compute='_compute_child_counts',
    )
    refund_count = fields.Integer(
        string='Refunds',
        compute='_compute_child_counts',
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    note = fields.Text(string='Notes')

    # ── SQL Constraints ───────────────────────────────────────────────────
    _sql_constraints = [
        (
            'student_unique',
            'UNIQUE(student_id)',
            'Only one deposit ledger is allowed per student.',
        ),
    ]

    # ── Display name ──────────────────────────────────────────────────────
    @api.depends('student_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            name = rec.student_id.display_name or 'New'
            rec.display_name = f'DEP/{name}'

    # ── Currency ──────────────────────────────────────────────────────────
    @api.depends('company_id', 'company_id.currency_id')
    def _compute_currency(self):
        for rec in self:
            rec.currency_id = (
                rec.company_id.currency_id
                or self.env.company.currency_id
            )

    # ── Balance computation ───────────────────────────────────────────────
    @api.depends(
        'student_id.fee_due_ids.paid_amount',
        'student_id.fee_due_ids.fee_nature',
        'adjustment_ids.amount',
        'adjustment_ids.state',
        'refund_ids.amount',
        'refund_ids.state',
    )
    def _compute_balances(self):
        for rec in self:
            # Collected from deposit dues
            deposit_dues = rec.student_id.fee_due_ids.filtered(
                lambda d: d.fee_nature == 'deposit'
            )
            collected = float_round(
                sum(deposit_dues.mapped('paid_amount')),
                precision_digits=2,
            )

            # Approved adjustments
            adjusted = float_round(
                sum(
                    rec.adjustment_ids
                    .filtered(lambda a: a.state == 'approved')
                    .mapped('amount')
                ),
                precision_digits=2,
            )

            # Completed refunds
            refunded = float_round(
                sum(
                    rec.refund_ids
                    .filtered(lambda r: r.state == 'done')
                    .mapped('amount')
                ),
                precision_digits=2,
            )

            rec.total_collected = collected
            rec.total_adjusted = adjusted
            rec.total_refunded = refunded
            rec.balance = float_round(
                collected - adjusted - refunded,
                precision_digits=2,
            )

    def _compute_child_counts(self):
        for rec in self:
            rec.adjustment_count = len(rec.adjustment_ids)
            rec.refund_count = len(rec.refund_ids)

    # ═════════════════════════════════════════════════════════════════════════
    # Factory
    # ═════════════════════════════════════════════════════════════════════════
    @api.model
    def get_or_create(self, student):
        """
        Return the deposit ledger for a student, creating it if it
        doesn't exist.
        """
        student.ensure_one()
        ledger = self.search([('student_id', '=', student.id)], limit=1)
        if not ledger:
            ledger = self.create({'student_id': student.id})
        return ledger

    # ═════════════════════════════════════════════════════════════════════════
    # Convenience Actions
    # ═════════════════════════════════════════════════════════════════════════
    def action_create_adjustment(self):
        """Open a form to create a new deposit adjustment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'New Deposit Adjustment — {self.student_id.display_name}',
            'res_model': 'edu.deposit.adjustment',
            'view_mode': 'form',
            'context': {
                'default_ledger_id': self.id,
            },
            'target': 'current',
        }

    def action_create_refund(self):
        """Open a form to create a new deposit refund."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'New Deposit Refund — {self.student_id.display_name}',
            'res_model': 'edu.deposit.refund',
            'view_mode': 'form',
            'context': {
                'default_ledger_id': self.id,
            },
            'target': 'current',
        }

    def action_view_adjustments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Adjustments — {self.student_id.display_name}',
            'res_model': 'edu.deposit.adjustment',
            'view_mode': 'list,form',
            'domain': [('ledger_id', '=', self.id)],
            'context': {'default_ledger_id': self.id},
        }

    def action_view_refunds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Refunds — {self.student_id.display_name}',
            'res_model': 'edu.deposit.refund',
            'view_mode': 'list,form',
            'domain': [('ledger_id', '=', self.id)],
            'context': {'default_ledger_id': self.id},
        }
