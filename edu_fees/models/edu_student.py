from odoo import api, fields, models
from odoo.tools import float_round


class EduStudent(models.Model):
    """
    Extend edu.student with finance summary fields and smart buttons.

    All monetary values are aggregated from the fee plans, dues, and
    payments linked through the student's enrollments.
    """

    _inherit = 'edu.student'

    # ═════════════════════════════════════════════════════════════════════════
    # Reverse Links
    # ═════════════════════════════════════════════════════════════════════════
    fee_plan_ids = fields.One2many(
        comodel_name='edu.student.fee.plan',
        inverse_name='student_id',
        string='Fee Plans',
    )
    fee_due_ids = fields.One2many(
        comodel_name='edu.student.fee.due',
        inverse_name='student_id',
        string='Fee Dues',
    )
    payment_ids = fields.One2many(
        comodel_name='edu.student.payment',
        inverse_name='student_id',
        string='Payments',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Finance Summary (computed)
    # ═════════════════════════════════════════════════════════════════════════
    finance_total_planned = fields.Monetary(
        string='Total Planned',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_total_discount = fields.Monetary(
        string='Total Discount',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_total_due = fields.Monetary(
        string='Total Due',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_total_paid = fields.Monetary(
        string='Total Paid',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_total_outstanding = fields.Monetary(
        string='Total Outstanding',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_total_deposit_paid = fields.Monetary(
        string='Total Deposit Paid',
        currency_field='finance_currency_id',
        compute='_compute_finance_summary',
    )
    finance_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Finance Currency',
        compute='_compute_finance_summary',
    )

    # ── Counts ────────────────────────────────────────────────────────────────
    fee_plan_count = fields.Integer(
        string='Fee Plans',
        compute='_compute_finance_counts',
    )
    fee_due_count = fields.Integer(
        string='Fee Dues',
        compute='_compute_finance_counts',
    )
    payment_count = fields.Integer(
        string='Payments',
        compute='_compute_finance_counts',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Compute Methods
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends(
        'fee_plan_ids.total_original',
        'fee_plan_ids.total_discount',
        'fee_plan_ids.total_final',
        'fee_plan_ids.currency_id',
        'fee_due_ids.due_amount',
        'fee_due_ids.paid_amount',
        'fee_due_ids.balance_amount',
        'fee_due_ids.fee_nature',
    )
    def _compute_finance_summary(self):
        for rec in self:
            plans = rec.fee_plan_ids
            dues = rec.fee_due_ids

            rec.finance_currency_id = (
                plans[:1].currency_id.id if plans else
                rec.company_id.currency_id.id
            )
            rec.finance_total_planned = sum(
                plans.mapped('total_original')
            )
            rec.finance_total_discount = sum(
                plans.mapped('total_discount')
            )
            rec.finance_total_due = sum(dues.mapped('due_amount'))
            rec.finance_total_paid = sum(dues.mapped('paid_amount'))
            rec.finance_total_outstanding = sum(
                dues.mapped('balance_amount')
            )

            # Deposit tracking — sum paid on deposit-nature dues
            deposit_dues = dues.filtered(
                lambda d: d.fee_nature == 'deposit'
            )
            rec.finance_total_deposit_paid = sum(
                deposit_dues.mapped('paid_amount')
            )

    @api.depends('fee_plan_ids', 'fee_due_ids', 'payment_ids')
    def _compute_finance_counts(self):
        for rec in self:
            rec.fee_plan_count = len(rec.fee_plan_ids)
            rec.fee_due_count = len(rec.fee_due_ids)
            rec.payment_count = len(rec.payment_ids)

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_fee_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Plans — {self.display_name}',
            'res_model': 'edu.student.fee.plan',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_view_fee_dues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Dues — {self.display_name}',
            'res_model': 'edu.student.fee.due',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payments — {self.display_name}',
            'res_model': 'edu.student.payment',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
