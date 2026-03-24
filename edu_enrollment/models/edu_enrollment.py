from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduEnrollment(models.Model):
    """
    Official enrollment record — the institutional activation of an
    accepted applicant.

    Created from a fully validated edu.admission.application once the
    offer is accepted, fees confirmed, and all readiness checks pass.

    Design principles:
    - Identity comes from applicant_profile_id (never flattened)
    - Academic placement and financial outcome are **snapshotted** at
      enrollment time so they remain historically stable
    - Links back to the source application are preserved for audit
    - Future student module can extend via student_id placeholder
    """

    _name = 'edu.enrollment'
    _description = 'Enrollment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'enrollment_date desc, id desc'
    _rec_name = 'enrollment_no'

    # ═════════════════════════════════════════════════════════════════════════
    # Locking configuration
    # ═════════════════════════════════════════════════════════════════════════
    _LOCKED_STATES = frozenset({'active', 'completed'})
    _CONTROLLED_STATES = frozenset({'confirmed'})
    _FROZEN_FIELDS = frozenset({
        'application_id', 'applicant_profile_id', 'program_id',
        'batch_id', 'academic_year_id', 'current_program_term_id',
        'fee_structure_id', 'payment_plan_id',
        'base_total_fee', 'scholarship_eligible_total',
        'total_scholarship_discount_amount', 'net_fee_after_scholarship',
        'scholarship_status', 'scholarship_cap_applied',
    })

    # ═════════════════════════════════════════════════════════════════════════
    # Identity / Source
    # ═════════════════════════════════════════════════════════════════════════
    enrollment_no = fields.Char(
        string='Enrollment No.',
        readonly=True,
        copy=False,
        index=True,
        help='Auto-assigned unique enrollment reference.',
    )
    active = fields.Boolean(default=True)

    application_id = fields.Many2one(
        comodel_name='edu.admission.application',
        string='Admission Application',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Source admission application from which this enrollment was created.',
    )
    admission_register_id = fields.Many2one(
        related='application_id.admission_register_id',
        string='Admission Register',
        store=True,
        index=True,
    )
    crm_lead_id = fields.Many2one(
        related='application_id.crm_lead_id',
        string='CRM Lead',
        store=True,
    )
    applicant_profile_id = fields.Many2one(
        comodel_name='edu.applicant.profile',
        string='Applicant Profile',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Applicant identity. Guardians and academic history are '
             'accessed through this link.',
    )
    partner_id = fields.Many2one(
        related='applicant_profile_id.partner_id',
        string='Contact',
        store=True,
        index=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Academic Placement (Snapshots)
    #
    # These are COPIED from the application at enrollment time.
    # They must remain historically stable even if the source application
    # or batch configuration changes later.
    # ═════════════════════════════════════════════════════════════════════════
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    current_program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Current Program Term',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Academic progression stage at time of enrollment '
             '(e.g. Semester 1).',
    )
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
        index=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Enrollment Context
    # ═════════════════════════════════════════════════════════════════════════
    enrollment_date = fields.Date(
        string='Enrollment Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    enrollment_type = fields.Selection(
        selection=[
            ('regular', 'Regular'),
            ('transfer', 'Transfer'),
            ('provisional', 'Provisional'),
            ('conditional', 'Conditional'),
        ],
        string='Enrollment Type',
        default='regular',
        required=True,
        tracking=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Financial Context (Snapshots)
    #
    # Copied from the admission application at enrollment time.
    # The enrollment module does NOT re-evaluate fees or scholarships.
    # These values are the basis for downstream billing.
    # ═════════════════════════════════════════════════════════════════════════
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        ondelete='restrict',
        tracking=True,
    )
    payment_plan_id = fields.Many2one(
        comodel_name='edu.fee.payment.plan',
        string='Payment Plan',
        ondelete='restrict',
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='fee_structure_id.currency_id',
        string='Currency',
    )
    base_total_fee = fields.Monetary(
        string='Base Total Fee',
        currency_field='currency_id',
        help='Total fee from fee structure at time of enrollment.',
    )
    scholarship_eligible_total = fields.Monetary(
        string='Scholarship-Eligible Total',
        currency_field='currency_id',
    )
    total_scholarship_discount_amount = fields.Monetary(
        string='Total Scholarship Discount',
        currency_field='currency_id',
    )
    net_fee_after_scholarship = fields.Monetary(
        string='Net Fee After Scholarship',
        currency_field='currency_id',
    )
    scholarship_status = fields.Selection(
        selection=[
            ('not_applicable', 'Not Applicable'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('partially_approved', 'Partially Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Scholarship Status',
    )
    scholarship_cap_applied = fields.Boolean(
        string='Scholarship Cap Applied',
        default=False,
    )
    fee_confirmed = fields.Boolean(
        string='Fee Confirmed',
        default=False,
    )
    fee_confirmation_date = fields.Datetime(
        string='Fee Confirmation Date',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Admission Outcome Snapshot
    # ═════════════════════════════════════════════════════════════════════════
    offer_status = fields.Selection(
        selection=[
            ('not_generated', 'Not Generated'),
            ('sent', 'Sent'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        string='Offer Status (Snapshot)',
    )
    offer_acceptance_date = fields.Datetime(
        string='Offer Acceptance Date',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # State
    # ═════════════════════════════════════════════════════════════════════════
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
            ('completed', 'Completed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Readiness / Computed
    # ═════════════════════════════════════════════════════════════════════════
    can_confirm = fields.Boolean(
        string='Can Confirm',
        compute='_compute_readiness_flags',
    )
    can_activate = fields.Boolean(
        string='Can Activate',
        compute='_compute_readiness_flags',
    )
    enrollment_block_reason = fields.Text(
        string='Enrollment Block Reason',
        compute='_compute_enrollment_block_reason',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Checklist
    # ═════════════════════════════════════════════════════════════════════════
    checklist_line_ids = fields.One2many(
        comodel_name='edu.enrollment.checklist.line',
        inverse_name='enrollment_id',
        string='Checklist',
    )
    checklist_complete = fields.Boolean(
        string='Checklist Complete',
        compute='_compute_checklist_status',
        store=True,
    )
    checklist_pending_count = fields.Integer(
        string='Pending Items',
        compute='_compute_checklist_status',
        store=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Guardian / Applicant Helpers
    # ═════════════════════════════════════════════════════════════════════════
    guardian_count = fields.Integer(
        string='Guardians',
        compute='_compute_guardian_count',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Future Integration
    # ═════════════════════════════════════════════════════════════════════════
    student_id = fields.Many2one(
        comodel_name='res.partner',
        string='Student Record',
        ondelete='set null',
        tracking=True,
        help='Placeholder for future edu.student integration. '
             'Currently points to the partner record.',
    )
    student_created = fields.Boolean(
        string='Student Created',
        compute='_compute_student_created',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Audit
    # ═════════════════════════════════════════════════════════════════════════
    enrolled_by_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Enrolled By',
        readonly=True,
        copy=False,
    )
    confirmed_by_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
    )
    activated_by_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Activated By',
        readonly=True,
        copy=False,
    )
    confirmed_on = fields.Datetime(
        string='Confirmed On',
        readonly=True,
        copy=False,
    )
    activated_on = fields.Datetime(
        string='Activated On',
        readonly=True,
        copy=False,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Notes
    # ═════════════════════════════════════════════════════════════════════════
    note = fields.Text(string='Notes')
    internal_note = fields.Html(string='Internal Notes')

    # ═════════════════════════════════════════════════════════════════════════
    # Company
    # ═════════════════════════════════════════════════════════════════════════
    company_id = fields.Many2one(
        related='program_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # SQL Constraints
    # ═════════════════════════════════════════════════════════════════════════
    _sql_constraints = [
        (
            'enrollment_no_unique',
            'UNIQUE(enrollment_no)',
            'Enrollment number must be unique.',
        ),
        (
            'application_active_unique',
            'UNIQUE(application_id)',
            'An enrollment already exists for this admission application.',
        ),
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('enrollment_no'):
                vals['enrollment_no'] = (
                    seq.next_by_code('edu.enrollment') or '/'
                )
            if not vals.get('enrolled_by_user_id'):
                vals['enrolled_by_user_id'] = self.env.uid
        records = super().create(vals_list)
        for rec in records:
            rec._validate_enrollment_integrity()
        return records

    def write(self, vals):
        # Enforce field locking by state
        changing_fields = set(vals.keys())
        frozen_change = self._FROZEN_FIELDS & changing_fields
        if frozen_change:
            for rec in self:
                if rec.state in self._LOCKED_STATES | self._CONTROLLED_STATES:
                    raise UserError(
                        f'Cannot modify {", ".join(frozen_change)} on '
                        f'enrollment "{rec.enrollment_no}" — record is '
                        f'in "{rec.state}" state.'
                    )
        return super().write(vals)

    # ═════════════════════════════════════════════════════════════════════════
    # Computed Fields
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends('state', 'checklist_complete', 'fee_confirmed',
                 'application_id', 'applicant_profile_id',
                 'program_id', 'batch_id', 'current_program_term_id')
    def _compute_readiness_flags(self):
        for rec in self:
            rec.can_confirm = (
                rec.state == 'draft'
                and rec.application_id
                and rec.applicant_profile_id
                and rec.program_id
                and rec.batch_id
                and rec.current_program_term_id
                and rec.fee_confirmed
            )
            rec.can_activate = (
                rec.state == 'confirmed'
                and rec.checklist_complete
            )

    def _compute_enrollment_block_reason(self):
        for rec in self:
            blocks = []
            if not rec.application_id:
                blocks.append('No admission application linked.')
            if not rec.applicant_profile_id:
                blocks.append('No applicant profile linked.')
            if not rec.program_id:
                blocks.append('Program is required.')
            if not rec.batch_id:
                blocks.append('Batch is required.')
            if not rec.current_program_term_id:
                blocks.append('Current program term is required.')
            if not rec.fee_confirmed:
                blocks.append('Fee must be confirmed on the application.')
            if not rec.checklist_complete:
                pending = rec.checklist_pending_count
                blocks.append(
                    f'{pending} checklist item(s) still pending.'
                    if pending else
                    'Checklist not complete.'
                )
            rec.enrollment_block_reason = (
                '\n'.join(blocks) if blocks else False
            )

    @api.depends(
        'checklist_line_ids.is_complete',
        'checklist_line_ids.is_required',
    )
    def _compute_checklist_status(self):
        for rec in self:
            required = rec.checklist_line_ids.filtered('is_required')
            if not required:
                rec.checklist_complete = True
                rec.checklist_pending_count = 0
            else:
                pending = required.filtered(lambda l: not l.is_complete)
                rec.checklist_pending_count = len(pending)
                rec.checklist_complete = len(pending) == 0

    def _compute_guardian_count(self):
        for rec in self:
            if rec.applicant_profile_id:
                rec.guardian_count = len(
                    rec.applicant_profile_id.guardian_rel_ids
                )
            else:
                rec.guardian_count = 0

    def _compute_student_created(self):
        for rec in self:
            rec.student_created = bool(rec.student_id)

    # ═════════════════════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════════════════════
    def _validate_enrollment_integrity(self):
        """
        Validate relational integrity after creation.
        Ensures the enrollment data is consistent and complete.
        """
        self.ensure_one()

        # Application must be in enrolled state or ready_for_enrollment
        app = self.application_id
        if app.state not in ('ready_for_enrollment', 'enrolled'):
            raise ValidationError(
                f'Application "{app.application_no}" is in state '
                f'"{app.state}" — only applications in '
                '"ready_for_enrollment" or "enrolled" state can be enrolled.'
            )

        # Applicant must match
        if self.applicant_profile_id != app.applicant_profile_id:
            raise ValidationError(
                'Applicant profile on enrollment does not match the '
                'admission application.'
            )

        # Batch must belong to program
        if self.batch_id and self.batch_id.program_id != self.program_id:
            raise ValidationError(
                f'Batch "{self.batch_id.name}" does not belong to '
                f'program "{self.program_id.name}".'
            )

        # Program term must belong to program
        if (self.current_program_term_id
                and self.current_program_term_id.program_id
                != self.program_id):
            raise ValidationError(
                f'Program term "{self.current_program_term_id.name}" '
                f'does not belong to program "{self.program_id.name}".'
            )

        # Check duplicate active enrollment for same applicant + batch
        domain = [
            ('id', '!=', self.id),
            ('applicant_profile_id', '=', self.applicant_profile_id.id),
            ('batch_id', '=', self.batch_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('state', 'not in', ['cancelled']),
        ]
        existing = self.search(domain, limit=1)
        if existing:
            raise ValidationError(
                f'An active enrollment already exists for this applicant '
                f'in batch "{self.batch_id.name}" / '
                f'year "{self.academic_year_id.name}": '
                f'{existing.enrollment_no}.'
            )

    @api.constrains('application_id', 'applicant_profile_id')
    def _check_applicant_consistency(self):
        for rec in self:
            if (rec.application_id and rec.applicant_profile_id
                    and rec.application_id.applicant_profile_id
                    != rec.applicant_profile_id):
                raise ValidationError(
                    'Applicant profile must match the admission application.'
                )

    @api.constrains('batch_id', 'program_id')
    def _check_batch_program(self):
        for rec in self:
            if rec.batch_id and rec.batch_id.program_id != rec.program_id:
                raise ValidationError(
                    f'Batch "{rec.batch_id.name}" does not belong to '
                    f'program "{rec.program_id.name}".'
                )

    @api.constrains('current_program_term_id', 'program_id')
    def _check_term_program(self):
        for rec in self:
            if (rec.current_program_term_id
                    and rec.current_program_term_id.program_id
                    != rec.program_id):
                raise ValidationError(
                    f'Program term "{rec.current_program_term_id.name}" '
                    f'does not belong to program "{rec.program_id.name}".'
                )

    # ═════════════════════════════════════════════════════════════════════════
    # Enrollment Creation from Application
    # ═════════════════════════════════════════════════════════════════════════
    @api.model
    def _prepare_vals_from_application(self, application):
        """
        Build enrollment values dict from a validated admission application.

        All academic and financial fields are snapshotted — copied as
        concrete values, not related fields — so they remain stable.
        """
        application.ensure_one()
        app = application

        # Resolve current program term from batch
        batch = app.batch_id
        if not batch:
            raise UserError(
                f'Application "{app.application_no}" has no batch assigned. '
                'A batch is required for enrollment.'
            )
        program_term = batch.current_program_term_id
        if not program_term:
            raise UserError(
                f'Batch "{batch.name}" has no current program term '
                'configured. Set the current progression stage on the '
                'batch before enrolling.'
            )

        return {
            # Source linkage
            'application_id': app.id,
            'applicant_profile_id': app.applicant_profile_id.id,
            # Academic placement (snapshots)
            'program_id': app.program_id.id,
            'batch_id': batch.id,
            'academic_year_id': app.academic_year_id.id,
            'current_program_term_id': program_term.id,
            # Financial context (snapshots)
            'fee_structure_id': (
                app.fee_structure_id.id if app.fee_structure_id else False
            ),
            'payment_plan_id': (
                app.selected_payment_plan_id.id
                if app.selected_payment_plan_id else False
            ),
            'base_total_fee': app.base_total_fee,
            'scholarship_eligible_total': app.scholarship_eligible_total,
            'total_scholarship_discount_amount': (
                app.total_scholarship_discount_amount
            ),
            'net_fee_after_scholarship': app.net_fee_after_scholarship,
            'scholarship_status': app.scholarship_status,
            'scholarship_cap_applied': app.scholarship_cap_applied,
            'fee_confirmed': app.fee_confirmed,
            'fee_confirmation_date': app.fee_confirmation_date,
            # Admission outcome (snapshots)
            'offer_status': app.offer_status,
            'offer_acceptance_date': app.offer_acceptance_date,
        }

    @api.model
    def action_create_from_application(self, application):
        """
        Public entry point: validate and create enrollment from an
        admission application.
        """
        application.ensure_one()
        self._check_application_enrollment_readiness(application)
        vals = self._prepare_vals_from_application(application)
        return self.create(vals)

    @api.model
    def _check_application_enrollment_readiness(self, application):
        """
        Full readiness validation before enrollment creation.
        Raises UserError with all blocking reasons.
        """
        application.ensure_one()
        app = application
        blocks = []

        if app.state != 'ready_for_enrollment':
            blocks.append(
                f'Application state is "{app.state}" — '
                'must be "ready_for_enrollment".'
            )
        if app.offer_status != 'accepted':
            blocks.append(
                f'Offer status is "{app.offer_status}" — '
                'must be "accepted".'
            )
        if not app.fee_confirmed:
            blocks.append('Fee is not confirmed.')
        if not app.selected_payment_plan_id:
            blocks.append('No payment plan selected.')
        if not app.applicant_profile_id:
            blocks.append('Applicant profile is missing.')
        if not app.program_id:
            blocks.append('Program is missing.')
        if not app.batch_id:
            blocks.append('Batch is missing.')
        if not app.academic_year_id:
            blocks.append('Academic year is missing.')

        # Batch must have current program term
        if app.batch_id and not app.batch_id.current_program_term_id:
            blocks.append(
                f'Batch "{app.batch_id.name}" has no current program '
                'term configured.'
            )

        # Check for existing enrollment from this application
        existing = self.search([
            ('application_id', '=', app.id),
            ('state', '!=', 'cancelled'),
        ], limit=1)
        if existing:
            blocks.append(
                f'An enrollment ({existing.enrollment_no}) already exists '
                'for this application.'
            )

        if blocks:
            raise UserError(
                f'Cannot create enrollment for "{app.application_no}":\n'
                + '\n'.join(f'  - {b}' for b in blocks)
            )

    # ═════════════════════════════════════════════════════════════════════════
    # State Transitions
    # ═════════════════════════════════════════════════════════════════════════
    def action_confirm(self):
        """
        Draft → Confirmed.
        Validates that all critical fields are present and consistent.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    f'Enrollment "{rec.enrollment_no}" is not in draft state.'
                )
            if not rec.can_confirm:
                raise UserError(
                    f'Cannot confirm enrollment "{rec.enrollment_no}":\n'
                    f'{rec.enrollment_block_reason or "Unknown issue."}'
                )
        self.write({
            'state': 'confirmed',
            'confirmed_by_user_id': self.env.uid,
            'confirmed_on': fields.Datetime.now(),
        })

    def action_activate(self):
        """
        Confirmed → Active.
        Requires all checklist items to be complete.
        """
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    f'Enrollment "{rec.enrollment_no}" must be confirmed '
                    'before activation.'
                )
            if not rec.can_activate:
                pending = rec.checklist_pending_count
                raise UserError(
                    f'Cannot activate enrollment "{rec.enrollment_no}" — '
                    f'{pending} required checklist item(s) still pending.'
                    if pending else
                    f'Cannot activate enrollment "{rec.enrollment_no}" — '
                    'checklist is not complete.'
                )
        self.write({
            'state': 'active',
            'activated_by_user_id': self.env.uid,
            'activated_on': fields.Datetime.now(),
        })

    def action_cancel(self):
        """
        Cancel enrollment. Allowed from draft or confirmed only.
        Active enrollments require admin action.
        """
        for rec in self:
            if rec.state in ('completed',):
                raise UserError(
                    f'Cannot cancel completed enrollment '
                    f'"{rec.enrollment_no}".'
                )
            if rec.state == 'active':
                raise UserError(
                    f'Cannot cancel active enrollment '
                    f'"{rec.enrollment_no}" — use administrative '
                    'procedures to withdraw an active enrollment.'
                )
        self.write({'state': 'cancelled'})

    def action_force_cancel(self):
        """
        Administrative cancellation — allowed from any non-completed state.
        Intended for enrollment admin only (controlled via group).
        """
        for rec in self:
            if rec.state == 'completed':
                raise UserError(
                    f'Cannot cancel completed enrollment '
                    f'"{rec.enrollment_no}".'
                )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        """Reset cancelled enrollment to draft."""
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    f'Only cancelled enrollments can be reset to draft. '
                    f'"{rec.enrollment_no}" is in "{rec.state}" state.'
                )
        self.write({
            'state': 'draft',
            'confirmed_by_user_id': False,
            'confirmed_on': False,
            'activated_by_user_id': False,
            'activated_on': False,
        })

    def action_complete(self):
        """
        Active → Completed.
        Marks enrollment as historically complete (graduated, etc.).
        """
        for rec in self:
            if rec.state != 'active':
                raise UserError(
                    f'Only active enrollments can be marked as completed. '
                    f'"{rec.enrollment_no}" is in "{rec.state}" state.'
                )
        self.write({'state': 'completed'})

    # ═════════════════════════════════════════════════════════════════════════
    # Future Student Integration
    # ═════════════════════════════════════════════════════════════════════════
    def _prepare_student_vals(self):
        """
        Prepare values for future student record creation.

        Returns a dict suitable for creating an edu.student record
        when that module becomes available. Currently serves as the
        integration contract.
        """
        self.ensure_one()
        return {
            'partner_id': self.partner_id.id,
            'applicant_profile_id': self.applicant_profile_id.id,
            'enrollment_id': self.id,
            'program_id': self.program_id.id,
            'batch_id': self.batch_id.id,
            'academic_year_id': self.academic_year_id.id,
            'current_program_term_id': self.current_program_term_id.id,
        }

    def action_create_student(self):
        """
        Hook for future student module integration.
        Override this method in edu_student to create the actual record.
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(
                'Student record can only be created from an active '
                'enrollment.'
            )
        student_model = self.env.get('edu.student')
        if student_model is None:
            raise UserError(
                'Student module is not installed. Install edu_student '
                'to create student records.'
            )
        vals = self._prepare_student_vals()
        student = student_model.create(vals)
        self.student_id = student.partner_id.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student',
            'res_id': student.id,
            'view_mode': 'form',
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_application(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.admission.application',
            'res_id': self.application_id.id,
            'view_mode': 'form',
        }

    def action_view_applicant_profile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.applicant.profile',
            'res_id': self.applicant_profile_id.id,
            'view_mode': 'form',
        }

    def action_view_guardians(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Guardians — {self.applicant_profile_id.full_name}',
            'res_model': 'edu.applicant.guardian.rel',
            'view_mode': 'list,form',
            'domain': [
                ('applicant_profile_id', '=',
                 self.applicant_profile_id.id),
            ],
        }
