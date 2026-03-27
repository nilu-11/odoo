from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduStudentFeePlan(models.Model):
    """
    Student-level fee plan — generated from the fee structure attached to
    an enrollment record.

    One plan per enrollment.  Lines are populated from fee-structure lines
    for each relevant progression stage, with scholarship discounts
    distributed proportionally across scholarship-eligible lines.

    Lifecycle:
        draft → confirmed → active → closed
    """

    _name = 'edu.student.fee.plan'
    _description = 'Student Fee Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    # ── Identity / Linkage ────────────────────────────────────────────────────
    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        ondelete='set null',
        tracking=True,
        index=True,
        help='Populated automatically when the student record is created '
             'from the enrollment.',
    )
    applicant_profile_id = fields.Many2one(
        related='enrollment_id.applicant_profile_id',
        string='Applicant',
        store=True,
        index=True,
    )

    # ── Academic Context (from enrollment snapshot) ───────────────────────────
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        required=True,
        ondelete='restrict',
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        required=True,
        ondelete='restrict',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        ondelete='restrict',
    )

    # ── Fee Structure Reference ───────────────────────────────────────────────
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        ondelete='restrict',
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='fee_structure_id.currency_id',
        string='Currency',
        store=True,
    )

    # ── Totals (computed from lines) ──────────────────────────────────────────
    total_original = fields.Monetary(
        string='Total Original',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_discount = fields.Monetary(
        string='Total Discount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    total_final = fields.Monetary(
        string='Total Final',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        comodel_name='edu.student.fee.plan.line',
        inverse_name='fee_plan_id',
        string='Plan Lines',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_totals',
        store=True,
    )

    # ── Convenience / Admin ───────────────────────────────────────────────────
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        related='program_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'enrollment_unique',
            'UNIQUE(enrollment_id)',
            'Only one fee plan is allowed per enrollment.',
        ),
    ]

    # ── Display name ──────────────────────────────────────────────────────────
    @api.depends('enrollment_id.enrollment_no', 'state')
    def _compute_display_name(self):
        for rec in self:
            enr = rec.enrollment_id.enrollment_no or 'New'
            rec.display_name = f'FP/{enr}'

    # ── Totals ────────────────────────────────────────────────────────────────
    @api.depends(
        'line_ids.original_amount',
        'line_ids.discount_amount',
        'line_ids.final_amount',
    )
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_original = sum(lines.mapped('original_amount'))
            rec.total_discount = sum(lines.mapped('discount_amount'))
            rec.total_final = sum(lines.mapped('final_amount'))
            rec.line_count = len(lines)

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    f'Fee plan for "{rec.enrollment_id.enrollment_no}" '
                    'is not in draft state.'
                )
            if not rec.line_ids:
                raise UserError(
                    'Cannot confirm an empty fee plan — add lines first.'
                )
        self.write({'state': 'confirmed'})

    def action_activate(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    f'Fee plan must be confirmed before activation.'
                )
        self.write({'state': 'active'})

    def action_close(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(
                    'Only active fee plans can be closed.'
                )
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('confirmed', 'closed'):
                raise UserError(
                    'Only confirmed or closed fee plans can be reset '
                    'to draft.'
                )
        self.write({'state': 'draft'})

    # ═════════════════════════════════════════════════════════════════════════
    # Fee Plan Generation
    # ═════════════════════════════════════════════════════════════════════════
    @api.model
    def action_generate_fee_plan(self, enrollment):
        """
        Generate a fee plan from an enrollment's fee structure.

        Steps:
          1. Read fee structure lines grouped by progression stage.
          2. For each line, create a plan line with original_amount.
          3. Distribute scholarship discount proportionally across
             scholarship-eligible lines.
          4. Set final_amount = original_amount − discount_amount.

        Returns the created edu.student.fee.plan record.
        """
        enrollment.ensure_one()

        if not enrollment.fee_structure_id:
            raise UserError(
                f'Enrollment "{enrollment.enrollment_no}" has no fee '
                'structure — cannot generate a fee plan.'
            )

        # Check for existing non-cancelled plan
        existing = self.search([
            ('enrollment_id', '=', enrollment.id),
        ], limit=1)
        if existing:
            raise UserError(
                f'A fee plan already exists for enrollment '
                f'"{enrollment.enrollment_no}". Delete or close the '
                'existing plan first.'
            )

        fee_structure = enrollment.fee_structure_id
        structure_lines = fee_structure.line_ids.sorted(
            key=lambda l: (l.progression_no, l.sequence)
        )

        if not structure_lines:
            raise UserError(
                f'Fee structure "{fee_structure.name}" has no lines — '
                'cannot generate a fee plan.'
            )

        # Determine default schedule template (full payment)
        default_template = self.env['edu.schedule.template'].search([
            ('schedule_type', '=', 'full'),
            ('active', '=', True),
            ('company_id', '=', enrollment.company_id.id),
        ], limit=1)

        # Create the plan
        plan = self.create({
            'enrollment_id': enrollment.id,
            'student_id': (
                enrollment.student_id.id
                if enrollment.student_id else False
            ),
            'program_id': enrollment.program_id.id,
            'batch_id': enrollment.batch_id.id,
            'academic_year_id': enrollment.academic_year_id.id,
            'fee_structure_id': fee_structure.id,
        })

        # Build plan lines
        total_scholarship_discount = enrollment.total_scholarship_discount_amount or 0.0
        scholarship_eligible_total = enrollment.scholarship_eligible_total or 0.0

        plan_line_vals = []
        for sl in structure_lines:
            original = sl.amount
            discount = 0.0

            # Distribute scholarship proportionally
            if (sl.scholarship_allowed
                    and total_scholarship_discount > 0
                    and scholarship_eligible_total > 0):
                share = original / scholarship_eligible_total
                discount = float_round(
                    total_scholarship_discount * share,
                    precision_digits=2,
                )
                # Cap discount at original amount
                discount = min(discount, original)

            final = float_round(
                original - discount,
                precision_digits=2,
            )

            plan_line_vals.append({
                'fee_plan_id': plan.id,
                'program_term_id': sl.program_term_id.id,
                'fee_head_id': sl.fee_head_id.id,
                'original_amount': original,
                'discount_amount': discount,
                'final_amount': final,
                'schedule_template_id': (
                    default_template.id if default_template else False
                ),
                'is_required_for_enrollment': (
                    sl.fee_head_id.is_required_for_enrollment
                ),
                'sequence': sl.sequence,
            })

        if plan_line_vals:
            self.env['edu.student.fee.plan.line'].create(plan_line_vals)

        return plan

    # ── Link student after creation ───────────────────────────────────────────
    def action_link_student(self, student):
        """
        Called when a student record is created from the enrollment.
        Links the student to this fee plan and all related dues / payments.
        """
        for rec in self:
            rec.student_id = student.id
            rec.line_ids.mapped('due_ids').write({
                'student_id': student.id,
            })
            # Link payments via dues
            payments = rec.line_ids.mapped(
                'due_ids.allocation_ids.payment_id'
            )
            payments.write({'student_id': student.id})


class EduStudentFeePlanLine(models.Model):
    """
    One line in a student fee plan — represents a single fee head
    charge for a specific progression stage.
    """

    _name = 'edu.student.fee.plan.line'
    _description = 'Student Fee Plan Line'
    _order = 'fee_plan_id, progression_no, sequence, id'
    _rec_name = 'fee_head_id'

    # ── Parent ────────────────────────────────────────────────────────────────
    fee_plan_id = fields.Many2one(
        comodel_name='edu.student.fee.plan',
        string='Fee Plan',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Progression ───────────────────────────────────────────────────────────
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Progression Stage',
        required=True,
        ondelete='restrict',
        index=True,
    )
    progression_no = fields.Integer(
        related='program_term_id.progression_no',
        string='Progression No.',
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

    # ── Amounts ───────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='fee_plan_id.currency_id',
        string='Currency',
        store=True,
    )
    original_amount = fields.Monetary(
        string='Original Amount',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    discount_amount = fields.Monetary(
        string='Discount Amount',
        currency_field='currency_id',
        default=0.0,
        help='Scholarship / discount amount applied to this line.',
    )
    final_amount = fields.Monetary(
        string='Final Amount',
        currency_field='currency_id',
        required=True,
        default=0.0,
        help='Amount the student must pay (original − discount).',
    )

    # ── Schedule ──────────────────────────────────────────────────────────────
    schedule_template_id = fields.Many2one(
        comodel_name='edu.schedule.template',
        string='Schedule Template',
        ondelete='restrict',
        help='Defines how this line is split into individual dues.',
    )

    # ── Control ───────────────────────────────────────────────────────────────
    is_required_for_enrollment = fields.Boolean(
        string='Required for Enrollment',
        default=False,
        help='Copied from the fee head at plan generation time.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    note = fields.Text(string='Note')

    # ── Dues (reverse link) ───────────────────────────────────────────────────
    due_ids = fields.One2many(
        comodel_name='edu.student.fee.due',
        inverse_name='fee_plan_line_id',
        string='Dues',
    )
    due_count = fields.Integer(
        string='Dues',
        compute='_compute_due_count',
    )

    # ── Related convenience ───────────────────────────────────────────────────
    enrollment_id = fields.Many2one(
        related='fee_plan_id.enrollment_id',
        string='Enrollment',
        store=True,
        index=True,
    )
    student_id = fields.Many2one(
        related='fee_plan_id.student_id',
        string='Student',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='fee_plan_id.company_id',
        string='Company',
        store=True,
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('due_ids')
    def _compute_due_count(self):
        for rec in self:
            rec.due_count = len(rec.due_ids)

    # ── Constraints ───────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_plan_line',
            'UNIQUE(fee_plan_id, program_term_id, fee_head_id)',
            'A fee head can only appear once per progression stage '
            'in a fee plan.',
        ),
    ]

    @api.constrains('original_amount', 'discount_amount', 'final_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.original_amount < 0:
                raise ValidationError(
                    f'Original amount cannot be negative for '
                    f'"{rec.fee_head_id.name}".'
                )
            if rec.discount_amount < 0:
                raise ValidationError(
                    f'Discount amount cannot be negative for '
                    f'"{rec.fee_head_id.name}".'
                )
            if float_compare(
                rec.discount_amount, rec.original_amount,
                precision_digits=2,
            ) > 0:
                raise ValidationError(
                    f'Discount ({rec.discount_amount}) cannot exceed '
                    f'original amount ({rec.original_amount}) for '
                    f'"{rec.fee_head_id.name}".'
                )
