from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduFeePaymentPlan(models.Model):
    """
    A configurable payment plan that describes HOW fees in a fee structure
    are collected from students.

    Two plan types:
    - Installment: fees are split across named installment slots, each slot
      specifying which fee heads are due at that point.
    - Monthly: a fixed monthly amount is billed over N months, optionally
      excluding certain fee heads (e.g. admission fee, university exam fee)
      from the monthly calculation.

    Multiple plans can coexist on one fee structure — e.g. an Installment Plan
    and a Monthly Plan can both be offered; the enrollment or billing module
    assigns the chosen plan to each student.
    """
    _name = 'edu.fee.payment.plan'
    _description = 'Fee Payment Plan'
    _order = 'fee_structure_id, sequence, id'
    _rec_name = 'name'

    # ── Parent structure ──────────────────────────────────────────────────────────
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Identity ──────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Plan Name',
        required=True,
        help='E.g. "Standard Installment Plan", "Monthly Payment Plan"',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    plan_type = fields.Selection(
        selection=[
            ('installment', 'Installment-Based'),
            ('monthly', 'Monthly'),
        ],
        string='Plan Type',
        required=True,
        default='installment',
        help=(
            'How fees are collected under this plan:\n'
            '• Installment-Based — fees split into named installment slots; '
            'each slot lists which fee heads are due at that point.\n'
            '• Monthly — a fixed amount billed each month over N months; '
            'configure which fee heads are excluded from the monthly calculation.'
        ),
    )

    # ── Monthly plan fields ───────────────────────────────────────────────────────
    months_count = fields.Integer(
        string='Months Count',
        default=0,
        help=(
            'Number of months over which fees are billed. '
            'Required when Plan Type is Monthly.'
        ),
    )
    excluded_fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        relation='edu_fee_payment_plan_excl_head_rel',
        column1='plan_id',
        column2='fee_head_id',
        string='Excluded Fee Heads',
        help=(
            'Fee heads that are NOT included in the monthly amount calculation. '
            'Typically: Admission Fee (paid at enrollment) and University Exam Fee '
            '(paid before exam). These are billed separately outside the monthly plan.'
        ),
    )

    # ── Installment plan fields ───────────────────────────────────────────────────
    installment_line_ids = fields.One2many(
        comodel_name='edu.fee.installment.line',
        inverse_name='plan_id',
        string='Installment Lines',
        help='Each line defines one installment slot and the fee heads due at that slot.',
    )

    # ── Convenience ───────────────────────────────────────────────────────────────
    note = fields.Text(string='Note', help='Internal notes or remarks about this plan.')
    company_id = fields.Many2one(
        related='fee_structure_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Python constraints ────────────────────────────────────────────────────────
    @api.constrains('plan_type', 'months_count')
    def _check_monthly_fields(self):
        for rec in self:
            if rec.plan_type == 'monthly' and rec.months_count <= 0:
                raise ValidationError(
                    f'Months count must be a positive number '
                    f'for monthly plan "{rec.name}".'
                )

    @api.constrains('plan_type', 'installment_line_ids')
    def _check_installment_fields(self):
        for rec in self:
            if rec.plan_type == 'installment' and not rec.installment_line_ids:
                raise ValidationError(
                    f'Installment plan "{rec.name}" must have '
                    'at least one installment line.'
                )

    # ── Onchange ──────────────────────────────────────────────────────────────────
    @api.onchange('plan_type')
    def _onchange_plan_type(self):
        if self.plan_type != 'monthly':
            self.months_count = 0
            self.excluded_fee_head_ids = [(5, 0, 0)]
        if self.plan_type != 'installment':
            self.installment_line_ids = [(5, 0, 0)]

    # ── Write / unlink locking ────────────────────────────────────────────────────
    def write(self, vals):
        for rec in self:
            if rec.fee_structure_id.state == 'closed':
                raise UserError(
                    f'Cannot modify payment plan "{rec.name}" — '
                    f'fee structure "{rec.fee_structure_id.name}" is closed.'
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.fee_structure_id.state != 'draft':
                raise UserError(
                    f'Cannot delete payment plan "{rec.name}" — '
                    f'fee structure "{rec.fee_structure_id.name}" is '
                    f'{rec.fee_structure_id.state}. Reset to Draft first.'
                )
        return super().unlink()


class EduFeeInstallmentLine(models.Model):
    """
    One slot within an installment payment plan.

    Example: Installment 1 → [Tuition Fee]
             Installment 2 → [Lab Fee, Library Fee]
             Installment 3 → [University Registration Fee]
    """
    _name = 'edu.fee.installment.line'
    _description = 'Fee Installment Line'
    _order = 'plan_id, sequence, id'
    _rec_name = 'label'

    plan_id = fields.Many2one(
        comodel_name='edu.fee.payment.plan',
        string='Payment Plan',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    label = fields.Char(
        string='Installment Label',
        required=True,
        help='E.g. "Installment 1", "At Admission", "Before Exam"',
    )
    fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        relation='edu_fee_installment_line_head_rel',
        column1='installment_line_id',
        column2='fee_head_id',
        string='Fee Heads',
        help='Fee heads due at this installment slot.',
    )
    note = fields.Text(string='Note')

    company_id = fields.Many2one(
        related='plan_id.fee_structure_id.company_id',
        string='Company',
        store=True,
    )
