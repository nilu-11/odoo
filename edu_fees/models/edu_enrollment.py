from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class EduEnrollment(models.Model):
    """
    Extend edu.enrollment with:
      - Fee plan / due / payment reverse links and summary fields.
      - Enrollment fee eligibility check (configurable via fee head
        ``is_required_for_enrollment`` flag).
      - Manager override for the enrollment fee block with full audit.
      - Auto-generation of fee plan and enrollment-required dues on
        enrollment creation.
    """

    _inherit = 'edu.enrollment'

    # ═════════════════════════════════════════════════════════════════════════
    # Fee Plan / Due / Payment Links
    # ═════════════════════════════════════════════════════════════════════════
    fee_plan_ids = fields.One2many(
        comodel_name='edu.student.fee.plan',
        inverse_name='enrollment_id',
        string='Fee Plans',
    )
    fee_plan_count = fields.Integer(
        string='Fee Plans',
        compute='_compute_fee_plan_count',
    )
    fee_due_ids = fields.One2many(
        comodel_name='edu.student.fee.due',
        inverse_name='enrollment_id',
        string='Fee Dues',
    )
    fee_due_count = fields.Integer(
        string='Fee Dues',
        compute='_compute_fee_due_count',
    )
    payment_ids = fields.One2many(
        comodel_name='edu.student.payment',
        inverse_name='enrollment_id',
        string='Payments',
    )
    payment_count = fields.Integer(
        string='Payments',
        compute='_compute_payment_count',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Enrollment Fee Summary (computed)
    # ═════════════════════════════════════════════════════════════════════════
    enrollment_required_total = fields.Monetary(
        string='Required Fees Total',
        currency_field='currency_id',
        compute='_compute_enrollment_fee_summary',
    )
    enrollment_required_paid = fields.Monetary(
        string='Required Fees Paid',
        currency_field='currency_id',
        compute='_compute_enrollment_fee_summary',
    )
    enrollment_required_balance = fields.Monetary(
        string='Required Fees Balance',
        currency_field='currency_id',
        compute='_compute_enrollment_fee_summary',
    )
    enrollment_fee_eligible = fields.Boolean(
        string='Fee Eligibility Met',
        compute='_compute_enrollment_fee_summary',
        store=True,
    )
    enrollment_fee_block_detail = fields.Text(
        string='Fee Block Detail',
        compute='_compute_enrollment_fee_summary',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Manager Override Fields
    # ═════════════════════════════════════════════════════════════════════════
    enrollment_fee_override_used = fields.Boolean(
        string='Fee Override Used',
        default=False,
        tracking=True,
        copy=False,
    )
    enrollment_fee_override_by = fields.Many2one(
        comodel_name='res.users',
        string='Override By',
        readonly=True,
        copy=False,
    )
    enrollment_fee_override_date = fields.Datetime(
        string='Override Date',
        readonly=True,
        copy=False,
    )
    enrollment_fee_override_reason = fields.Text(
        string='Override Reason',
        copy=False,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Computed Fields
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_fee_plan_count(self):
        for rec in self:
            rec.fee_plan_count = len(rec.fee_plan_ids)

    def _compute_fee_due_count(self):
        for rec in self:
            rec.fee_due_count = len(rec.fee_due_ids)

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends(
        'fee_due_ids.due_amount',
        'fee_due_ids.paid_amount',
        'fee_due_ids.balance_amount',
        'fee_due_ids.is_required_for_enrollment',
        'fee_due_ids.state',
        'enrollment_fee_override_used',
    )
    def _compute_enrollment_fee_summary(self):
        for rec in self:
            required_dues = rec.fee_due_ids.filtered(
                'is_required_for_enrollment'
            )
            total = sum(required_dues.mapped('due_amount'))
            paid = sum(required_dues.mapped('paid_amount'))
            # A due marked 'paid' via accounting sync has state='paid' but
            # balance_amount may still reflect internal allocations only.
            # Treat state='paid' dues as fully cleared for eligibility.
            effective_balance = sum(
                0.0 if d.state == 'paid' else d.balance_amount
                for d in required_dues
            )
            balance = sum(required_dues.mapped('balance_amount'))

            rec.enrollment_required_total = total
            rec.enrollment_required_paid = paid
            rec.enrollment_required_balance = balance

            if rec.enrollment_fee_override_used:
                rec.enrollment_fee_eligible = True
                rec.enrollment_fee_block_detail = False
            elif not required_dues:
                # No required dues configured — no block
                rec.enrollment_fee_eligible = True
                rec.enrollment_fee_block_detail = False
            elif float_compare(effective_balance, 0.0, precision_digits=2) <= 0:
                rec.enrollment_fee_eligible = True
                rec.enrollment_fee_block_detail = False
            else:
                rec.enrollment_fee_eligible = False
                unpaid_heads = required_dues.filtered(
                    lambda d: d.state != 'paid' and float_compare(
                        d.balance_amount, 0.0, precision_digits=2
                    ) > 0
                ).mapped('fee_head_id.name')
                rec.enrollment_fee_block_detail = (
                    'Outstanding required fees:\n'
                    + '\n'.join(f'  - {h}' for h in unpaid_heads)
                    + f'\n\nTotal balance: {effective_balance:.2f}'
                )

    # ═════════════════════════════════════════════════════════════════════════
    # Override Readiness Computation
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends(
        'state', 'checklist_complete', 'fee_confirmed',
        'application_id', 'applicant_profile_id',
        'program_id', 'batch_id', 'current_program_term_id',
        'enrollment_fee_eligible',
    )
    def _compute_readiness_flags(self):
        """Extend the base readiness check to include fee eligibility."""
        for rec in self:
            rec.can_confirm = (
                rec.state == 'draft'
                and rec.application_id
                and rec.applicant_profile_id
                and rec.program_id
                and rec.batch_id
                and rec.current_program_term_id
                and rec.fee_confirmed
                and rec.enrollment_fee_eligible
            )
            rec.can_activate = (
                rec.state == 'confirmed'
                and rec.checklist_complete
            )

    def _compute_enrollment_block_reason(self):
        """Extend block reasons with fee payment details."""
        super()._compute_enrollment_block_reason()
        for rec in self:
            if not rec.enrollment_fee_eligible:
                detail = rec.enrollment_fee_block_detail or (
                    'Required enrollment fees are not fully paid.'
                )
                existing = rec.enrollment_block_reason or ''
                if existing:
                    rec.enrollment_block_reason = (
                        existing + '\n' + detail
                    )
                else:
                    rec.enrollment_block_reason = detail

    # ═════════════════════════════════════════════════════════════════════════
    # Enrollment Fee Eligibility Check
    # ═════════════════════════════════════════════════════════════════════════
    def check_enrollment_fee_eligibility(self):
        """
        Public check method — returns True if enrollment fee
        requirements are satisfied (all required fees paid or override
        used).

        Raises UserError with details if not eligible and no override.
        """
        self.ensure_one()
        if self.enrollment_fee_eligible:
            return True

        raise UserError(
            f'Enrollment "{self.enrollment_no}" cannot be confirmed.\n\n'
            f'{self.enrollment_fee_block_detail or "Required fees are outstanding."}\n\n'
            'Pay the outstanding required fees or request a manager '
            'override.'
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Manager Override
    # ═════════════════════════════════════════════════════════════════════════
    def action_override_enrollment_fee_block(self):
        """
        Record a manager override to bypass the enrollment fee block.

        Requires the user to belong to
        ``edu_fees.group_enrollment_fee_override``.
        Records the override with full audit trail.
        """
        self.ensure_one()
        if self.enrollment_fee_eligible and not self.enrollment_fee_override_used:
            raise UserError(
                'No override needed — enrollment fee requirements are '
                'already satisfied.'
            )
        if not self.env.user.has_group(
            'edu_fees.group_enrollment_fee_override'
        ):
            raise UserError(
                'You do not have permission to override the enrollment '
                'fee block. Contact your finance manager.'
            )
        if not self.enrollment_fee_override_reason:
            raise UserError(
                'An override reason is required. Please enter the '
                'reason before overriding.'
            )
        self.write({
            'enrollment_fee_override_used': True,
            'enrollment_fee_override_by': self.env.uid,
            'enrollment_fee_override_date': fields.Datetime.now(),
        })
        self.message_post(
            body=(
                f'<strong>Enrollment fee override recorded.</strong><br/>'
                f'Override by: {self.env.user.name}<br/>'
                f'Reason: {self.enrollment_fee_override_reason}'
            ),
            message_type='notification',
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Override Confirm to enforce fee eligibility
    # ═════════════════════════════════════════════════════════════════════════
    def action_confirm(self):
        """
        Extended: validate enrollment fee eligibility before confirming.
        """
        for rec in self:
            if not rec.enrollment_fee_eligible:
                rec.check_enrollment_fee_eligibility()
        return super().action_confirm()

    # ═════════════════════════════════════════════════════════════════════════
    # Auto-generate Fee Plan on Enrollment Creation
    # ═════════════════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.fee_structure_id:
                try:
                    plan = self.env[
                        'edu.student.fee.plan'
                    ].action_generate_fee_plan(rec)
                    # Auto-generate dues for enrollment-required fees
                    self.env[
                        'edu.student.fee.due'
                    ].action_generate_enrollment_dues(plan)
                except Exception:
                    # Log but don't block enrollment creation
                    rec.message_post(
                        body=(
                            '<strong>Auto fee plan generation failed.'
                            '</strong><br/>'
                            'Use the "Generate Fee Plan" button to retry.'
                        ),
                        message_type='notification',
                    )
        return records

    # ═════════════════════════════════════════════════════════════════════════
    # Manual Fee Plan Generation
    # ═════════════════════════════════════════════════════════════════════════
    def action_generate_fee_plan(self):
        """Manual trigger for fee plan generation from the enrollment form."""
        self.ensure_one()
        plan = self.env['edu.student.fee.plan'].action_generate_fee_plan(self)
        self.env['edu.student.fee.due'].action_generate_enrollment_dues(plan)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student.fee.plan',
            'res_id': plan.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_generate_all_dues(self):
        """Generate dues for ALL plan lines (not just enrollment-required)."""
        self.ensure_one()
        plan = self.fee_plan_ids[:1]
        if not plan:
            raise UserError(
                'No fee plan exists. Generate a fee plan first.'
            )
        self.env['edu.student.fee.due'].action_generate_dues(plan)
        return True

    # ═════════════════════════════════════════════════════════════════════════
    # Student Creation Hook — link fee data to student
    # ═════════════════════════════════════════════════════════════════════════
    def action_create_student(self):
        """
        Extend student creation to link fee plans, dues, and payments
        to the newly created student record.
        """
        result = super().action_create_student()
        if self.student_id:
            for plan in self.fee_plan_ids:
                plan.action_link_student(self.student_id)
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_fee_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Plans — {self.enrollment_no}',
            'res_model': 'edu.student.fee.plan',
            'view_mode': 'list,form',
            'domain': [('enrollment_id', '=', self.id)],
            'context': {'default_enrollment_id': self.id},
        }

    def action_view_fee_dues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Dues — {self.enrollment_no}',
            'res_model': 'edu.student.fee.due',
            'view_mode': 'list,form',
            'domain': [('enrollment_id', '=', self.id)],
            'context': {'default_enrollment_id': self.id},
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payments — {self.enrollment_no}',
            'res_model': 'edu.student.payment',
            'view_mode': 'list,form',
            'domain': [('enrollment_id', '=', self.id)],
            'context': {'default_enrollment_id': self.id},
        }
