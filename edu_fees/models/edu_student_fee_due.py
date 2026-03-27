from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduStudentFeeDue(models.Model):
    """
    An individual payable record generated from a student fee plan line.

    Each due represents a concrete amount owed on a specific date.
    A single plan line may generate one or more dues depending on the
    schedule template (full = 1 due, installment = N dues).

    States:
        draft → due → partial → paid
                 ↳ overdue (set by cron or manual action)
    """

    _name = 'edu.student.fee.due'
    _description = 'Student Fee Due'
    _inherit = ['mail.thread']
    _order = 'due_date, id'
    _rec_name = 'display_name'

    # ── Linkage ───────────────────────────────────────────────────────────────
    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        required=True,
        ondelete='restrict',
        index=True,
    )
    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        ondelete='set null',
        index=True,
    )
    fee_plan_line_id = fields.Many2one(
        comodel_name='edu.student.fee.plan.line',
        string='Fee Plan Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    fee_plan_id = fields.Many2one(
        related='fee_plan_line_id.fee_plan_id',
        string='Fee Plan',
        store=True,
        index=True,
    )

    # ── Fee Head ──────────────────────────────────────────────────────────────
    fee_head_id = fields.Many2one(
        comodel_name='edu.fee.head',
        string='Fee Head',
        required=True,
        ondelete='restrict',
        index=True,
    )
    fee_nature = fields.Selection(
        related='fee_head_id.fee_nature',
        string='Fee Nature',
        store=True,
    )
    is_required_for_enrollment = fields.Boolean(
        related='fee_head_id.is_required_for_enrollment',
        string='Required for Enrollment',
        store=True,
        index=True,
    )

    # ── Progression ───────────────────────────────────────────────────────────
    program_term_id = fields.Many2one(
        related='fee_plan_line_id.program_term_id',
        string='Progression Stage',
        store=True,
        index=True,
    )
    progression_no = fields.Integer(
        related='fee_plan_line_id.progression_no',
        string='Progression No.',
        store=True,
    )

    # ── Schedule ──────────────────────────────────────────────────────────────
    installment_no = fields.Integer(
        string='Installment No.',
        default=1,
    )
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Amounts ───────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='fee_plan_line_id.currency_id',
        string='Currency',
        store=True,
    )
    original_amount = fields.Monetary(
        string='Original Amount',
        currency_field='currency_id',
        help='Amount before any discount (this installment share).',
    )
    discount_amount = fields.Monetary(
        string='Discount Amount',
        currency_field='currency_id',
        default=0.0,
    )
    due_amount = fields.Monetary(
        string='Due Amount',
        currency_field='currency_id',
        required=True,
        help='Net amount the student must pay for this due.',
    )
    paid_amount = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        compute='_compute_paid_balance',
        store=True,
        help='Total allocated from payments.',
    )
    balance_amount = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        compute='_compute_paid_balance',
        store=True,
        help='Remaining unpaid balance.',
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('due', 'Due'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # ── Allocations (reverse link) ────────────────────────────────────────────
    allocation_ids = fields.One2many(
        comodel_name='edu.student.payment.allocation',
        inverse_name='due_id',
        string='Payment Allocations',
    )

    # ── Convenience ───────────────────────────────────────────────────────────
    note = fields.Text(string='Note')
    company_id = fields.Many2one(
        related='enrollment_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Display name ──────────────────────────────────────────────────────────
    @api.depends('fee_head_id', 'installment_no', 'due_date')
    def _compute_display_name(self):
        for rec in self:
            head = rec.fee_head_id.name or ''
            date_str = rec.due_date.strftime('%Y-%m-%d') if rec.due_date else ''
            rec.display_name = f'{head} #{rec.installment_no} ({date_str})'

    # ── Paid / Balance computation ────────────────────────────────────────────
    @api.depends(
        'due_amount',
        'allocation_ids.allocated_amount',
        'allocation_ids.payment_id.state',
    )
    def _compute_paid_balance(self):
        for rec in self:
            paid = sum(
                alloc.allocated_amount
                for alloc in rec.allocation_ids
                if alloc.payment_id.state == 'posted'
            )
            rec.paid_amount = float_round(paid, precision_digits=2)
            rec.balance_amount = float_round(
                rec.due_amount - rec.paid_amount, precision_digits=2
            )

    # ── State management ──────────────────────────────────────────────────────
    def action_set_due(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft dues can be set to due.')
        self.write({'state': 'due'})

    def action_mark_overdue(self):
        for rec in self:
            if rec.state not in ('due', 'partial'):
                raise UserError(
                    'Only dues in "due" or "partial" state can be '
                    'marked overdue.'
                )
        self.write({'state': 'overdue'})

    def _update_state_from_payment(self):
        """
        Recompute state based on current paid vs due amounts.
        Called after payment allocation or cancellation.
        """
        for rec in self:
            if rec.state in ('draft',):
                continue
            prec = 2
            if float_compare(rec.paid_amount, rec.due_amount,
                             precision_digits=prec) >= 0:
                rec.state = 'paid'
            elif float_compare(rec.paid_amount, 0.0,
                               precision_digits=prec) > 0:
                rec.state = 'partial'
            else:
                # Revert to due or overdue depending on date
                if (rec.due_date
                        and rec.due_date < fields.Date.context_today(rec)):
                    rec.state = 'overdue'
                else:
                    rec.state = 'due'

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('due_amount')
    def _check_due_amount(self):
        for rec in self:
            if rec.due_amount < 0:
                raise ValidationError(
                    f'Due amount cannot be negative for '
                    f'"{rec.fee_head_id.name}".'
                )

    # ═════════════════════════════════════════════════════════════════════════
    # Due Generation
    # ═════════════════════════════════════════════════════════════════════════
    @api.model
    def action_generate_dues(self, fee_plan, base_date=None):
        """
        Generate due records for all lines of a fee plan.

        Each plan line is expanded into one or more dues based on its
        schedule template.  If no template is assigned, a single due
        for the full amount is created.

        Args:
            fee_plan: edu.student.fee.plan recordset (single)
            base_date: date from which offset_days are calculated.
                       Defaults to enrollment_date.
        """
        fee_plan.ensure_one()

        if not base_date:
            base_date = fee_plan.enrollment_id.enrollment_date

        if not base_date:
            raise UserError(
                'Cannot generate dues — enrollment date is not set.'
            )

        # Remove existing draft dues to allow regeneration
        existing_draft = self.search([
            ('fee_plan_id', '=', fee_plan.id),
            ('state', '=', 'draft'),
        ])
        if existing_draft:
            existing_draft.unlink()

        # Check no non-draft dues exist (safety)
        existing_active = self.search([
            ('fee_plan_id', '=', fee_plan.id),
            ('state', '!=', 'draft'),
        ], limit=1)
        if existing_active:
            raise UserError(
                'Cannot regenerate dues — active/paid dues already '
                'exist. Cancel or reverse them first.'
            )

        due_vals_list = []
        for line in fee_plan.line_ids:
            if float_compare(line.final_amount, 0.0,
                             precision_digits=2) <= 0:
                continue

            template = line.schedule_template_id
            if template:
                installments = template.get_installments()
            else:
                # Default: single full-amount due
                installments = [
                    {'installment_no': 1, 'percentage': 100.0,
                     'offset_days': 0}
                ]

            for inst in installments:
                pct = inst['percentage'] / 100.0
                inst_original = float_round(
                    line.original_amount * pct, precision_digits=2
                )
                inst_discount = float_round(
                    line.discount_amount * pct, precision_digits=2
                )
                inst_due = float_round(
                    line.final_amount * pct, precision_digits=2
                )
                due_date = base_date + timedelta(days=inst['offset_days'])

                due_vals_list.append({
                    'enrollment_id': fee_plan.enrollment_id.id,
                    'student_id': (
                        fee_plan.student_id.id
                        if fee_plan.student_id else False
                    ),
                    'fee_plan_line_id': line.id,
                    'fee_head_id': line.fee_head_id.id,
                    'installment_no': inst['installment_no'],
                    'due_date': due_date,
                    'original_amount': inst_original,
                    'discount_amount': inst_discount,
                    'due_amount': inst_due,
                })

        if due_vals_list:
            self.create(due_vals_list)

        return True

    @api.model
    def action_generate_enrollment_dues(self, fee_plan, base_date=None):
        """
        Generate dues ONLY for fee plan lines flagged as
        is_required_for_enrollment.

        Used during enrollment to create the minimal set of dues that
        must be paid before enrollment can be confirmed.
        """
        fee_plan.ensure_one()

        if not base_date:
            base_date = fee_plan.enrollment_id.enrollment_date

        if not base_date:
            raise UserError(
                'Cannot generate dues — enrollment date is not set.'
            )

        required_lines = fee_plan.line_ids.filtered(
            'is_required_for_enrollment'
        )

        due_vals_list = []
        for line in required_lines:
            if float_compare(line.final_amount, 0.0,
                             precision_digits=2) <= 0:
                continue

            template = line.schedule_template_id
            if template:
                installments = template.get_installments()
            else:
                installments = [
                    {'installment_no': 1, 'percentage': 100.0,
                     'offset_days': 0}
                ]

            for inst in installments:
                pct = inst['percentage'] / 100.0
                inst_original = float_round(
                    line.original_amount * pct, precision_digits=2
                )
                inst_discount = float_round(
                    line.discount_amount * pct, precision_digits=2
                )
                inst_due = float_round(
                    line.final_amount * pct, precision_digits=2
                )
                due_date = base_date + timedelta(days=inst['offset_days'])

                due_vals_list.append({
                    'enrollment_id': fee_plan.enrollment_id.id,
                    'student_id': (
                        fee_plan.student_id.id
                        if fee_plan.student_id else False
                    ),
                    'fee_plan_line_id': line.id,
                    'fee_head_id': line.fee_head_id.id,
                    'installment_no': inst['installment_no'],
                    'due_date': due_date,
                    'original_amount': inst_original,
                    'discount_amount': inst_discount,
                    'due_amount': inst_due,
                    'state': 'due',
                })

        if due_vals_list:
            self.create(due_vals_list)

        return True
