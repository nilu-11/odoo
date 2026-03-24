from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduAdmissionApplication(models.Model):
    """
    The central formal admission record.

    Identity and guardian data live in edu.applicant.profile and related
    models — this record holds workflow state, fee context, scholarship
    outcome, and offer lifecycle.
    """

    _name = 'edu.admission.application'
    _description = 'Admission Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'application_no'

    # ═════════════════════════════════════════════════════════════════════════
    # Identity / Linkage
    # ═════════════════════════════════════════════════════════════════════════
    application_no = fields.Char(
        string='Application No.',
        readonly=True,
        copy=False,
        index=True,
    )
    active = fields.Boolean(default=True)

    applicant_profile_id = fields.Many2one(
        comodel_name='edu.applicant.profile',
        string='Applicant Profile',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Structured applicant identity. Guardians and academic history '
             'are accessed through this link.',
    )
    partner_id = fields.Many2one(
        related='applicant_profile_id.partner_id',
        string='Contact',
        store=True,
        index=True,
    )
    crm_lead_id = fields.Many2one(
        comodel_name='crm.lead',
        string='CRM Lead',
        ondelete='set null',
        tracking=True,
        index=True,
        help='Source CRM lead if this application was created by conversion.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Academic Context
    # ═════════════════════════════════════════════════════════════════════════
    admission_register_id = fields.Many2one(
        comodel_name='edu.admission.register',
        string='Admission Register',
        ondelete='restrict',
        tracking=True,
        index=True,
        domain="[('state', '=', 'open')]",
    )
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
        ondelete='restrict',
        tracking=True,
        domain="[('program_id', '=', program_id), "
               "('academic_year_id', '=', academic_year_id)]",
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Fee Context
    # ═════════════════════════════════════════════════════════════════════════
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        ondelete='restrict',
        tracking=True,
    )
    available_payment_plan_ids = fields.Many2many(
        comodel_name='edu.fee.payment.plan',
        relation='edu_admission_app_payment_plan_rel',
        column1='application_id',
        column2='plan_id',
        string='Available Payment Plans',
    )
    selected_payment_plan_id = fields.Many2one(
        comodel_name='edu.fee.payment.plan',
        string='Selected Payment Plan',
        ondelete='restrict',
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='fee_structure_id.currency_id',
        string='Currency',
    )

    # Fee computed fields
    base_total_fee = fields.Monetary(
        string='Base Total Fee',
        currency_field='currency_id',
        compute='_compute_fee_preview',
        store=True,
    )
    scholarship_eligible_total = fields.Monetary(
        string='Scholarship-Eligible Total',
        currency_field='currency_id',
        compute='_compute_fee_preview',
        store=True,
    )
    total_scholarship_discount_amount = fields.Monetary(
        string='Total Scholarship Discount',
        currency_field='currency_id',
        compute='_compute_scholarship_summary',
        store=True,
    )
    net_fee_after_scholarship = fields.Monetary(
        string='Net Fee After Scholarship',
        currency_field='currency_id',
        compute='_compute_scholarship_summary',
        store=True,
    )
    fee_summary_display = fields.Text(
        string='Fee Summary',
        compute='_compute_fee_summary_display',
    )

    # Fee confirmation
    fee_confirmed = fields.Boolean(
        string='Fee Confirmed',
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
    )
    fee_confirmation_date = fields.Datetime(
        string='Fee Confirmation Date',
        readonly=True,
        copy=False,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Scholarship Summary
    # ═════════════════════════════════════════════════════════════════════════
    scholarship_status = fields.Selection(
        selection=[
            ('not_applicable', 'Not Applicable'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('partially_approved', 'Partially Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Scholarship Status',
        default='not_applicable',
        tracking=True,
        compute='_compute_scholarship_summary',
        store=True,
    )
    scholarship_cap_applied = fields.Boolean(
        string='Scholarship Cap Applied',
        compute='_compute_scholarship_summary',
        store=True,
    )
    scholarship_note_summary = fields.Text(
        string='Scholarship Summary Notes',
        compute='_compute_scholarship_summary',
        store=True,
    )
    scholarship_review_ids = fields.One2many(
        comodel_name='edu.admission.scholarship.review',
        inverse_name='application_id',
        string='Scholarship Reviews',
    )
    scholarship_review_count = fields.Integer(
        string='Scholarship Reviews',
        compute='_compute_scholarship_review_count',
    )
    approved_scholarship_count = fields.Integer(
        string='Approved Scholarships',
        compute='_compute_scholarship_review_count',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Offer Fields
    # ═════════════════════════════════════════════════════════════════════════
    offer_status = fields.Selection(
        selection=[
            ('not_generated', 'Not Generated'),
            ('sent', 'Sent'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        string='Offer Status',
        default='not_generated',
        tracking=True,
    )
    offer_letter_generated = fields.Boolean(
        string='Offer Letter Generated',
        default=False,
        copy=False,
    )
    offer_letter_date = fields.Date(
        string='Offer Letter Date',
        copy=False,
    )
    offer_letter_ref = fields.Char(
        string='Offer Letter Ref.',
        copy=False,
    )
    offer_expiry_date = fields.Date(
        string='Offer Expiry Date',
        tracking=True,
    )
    offer_acceptance_date = fields.Datetime(
        string='Offer Acceptance Date',
        readonly=True,
        copy=False,
    )
    offer_rejection_reason = fields.Text(
        string='Offer Rejection Reason',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Process Control / State
    # ═════════════════════════════════════════════════════════════════════════
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under Review'),
            ('scholarship_review', 'Scholarship Review'),
            ('offered', 'Offered'),
            ('offer_accepted', 'Offer Accepted'),
            ('offer_rejected', 'Offer Rejected'),
            ('ready_for_enrollment', 'Ready for Enrollment'),
            ('enrolled', 'Enrolled'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    review_complete = fields.Boolean(
        string='Review Complete',
        default=False,
        tracking=True,
    )
    documents_complete = fields.Boolean(
        string='Documents Complete',
        default=False,
        help='Placeholder for future document management integration.',
    )

    # Computed process flags
    can_generate_offer = fields.Boolean(
        compute='_compute_process_flags',
    )
    can_accept_offer = fields.Boolean(
        compute='_compute_process_flags',
    )
    can_mark_ready_for_enrollment = fields.Boolean(
        compute='_compute_process_flags',
    )
    can_enroll = fields.Boolean(
        compute='_compute_process_flags',
    )
    enrollment_ready = fields.Boolean(
        string='Enrollment Ready',
        compute='_compute_enrollment_readiness',
    )
    enrollment_block_reason = fields.Text(
        string='Enrollment Block Reason',
        compute='_compute_enrollment_readiness',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Audit / Ownership
    # ═════════════════════════════════════════════════════════════════════════
    assigned_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned To',
        tracking=True,
        domain="[('share', '=', False)]",
    )
    internal_note = fields.Html(string='Internal Notes')
    note = fields.Text(string='Notes')

    # ═════════════════════════════════════════════════════════════════════════
    # Frozen-state tracking
    # ═════════════════════════════════════════════════════════════════════════
    _FROZEN_STATES = frozenset({
        'offer_accepted', 'ready_for_enrollment', 'enrolled',
    })
    _FROZEN_FIELDS = frozenset({
        'applicant_profile_id', 'admission_register_id', 'program_id',
        'batch_id', 'academic_year_id', 'fee_structure_id',
        'selected_payment_plan_id',
    })

    # ═════════════════════════════════════════════════════════════════════════
    # SQL Constraints
    # ═════════════════════════════════════════════════════════════════════════
    _sql_constraints = [
        (
            'application_no_unique',
            'UNIQUE(application_no)',
            'Application number must be unique.',
        ),
    ]

    # ═════════════════════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('application_no'):
                vals['application_no'] = (
                    seq.next_by_code('edu.admission.application') or '/'
                )
        records = super().create(vals_list)
        # Auto-populate from register if set
        for rec in records:
            if rec.admission_register_id and not rec.fee_structure_id:
                rec._populate_from_register()
        return records

    def write(self, vals):
        # Enforce frozen fields after offer acceptance
        frozen_change = self._FROZEN_FIELDS & vals.keys()
        if frozen_change:
            for rec in self:
                if rec.state in self._FROZEN_STATES:
                    raise UserError(
                        f'Cannot modify {", ".join(frozen_change)} on '
                        f'application "{rec.application_no}" — '
                        f'the application is in "{rec.state}" state. '
                        'These fields are frozen after offer acceptance.'
                    )
        return super().write(vals)

    # ═════════════════════════════════════════════════════════════════════════
    # Duplicate Prevention
    # ═════════════════════════════════════════════════════════════════════════
    @api.constrains('applicant_profile_id', 'admission_register_id')
    def _check_duplicate_application(self):
        for rec in self:
            if not rec.admission_register_id:
                continue
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('applicant_profile_id', '=', rec.applicant_profile_id.id),
                ('admission_register_id', '=', rec.admission_register_id.id),
                ('state', 'not in', ['cancelled']),
                ('active', '=', True),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'Applicant "{rec.applicant_profile_id.full_name}" already '
                    f'has an active application in register '
                    f'"{rec.admission_register_id.name}" '
                    f'({duplicate.application_no}).'
                )

    @api.constrains('selected_payment_plan_id', 'fee_structure_id')
    def _check_payment_plan_belongs(self):
        for rec in self:
            if (
                rec.selected_payment_plan_id
                and rec.fee_structure_id
                and rec.selected_payment_plan_id.fee_structure_id
                != rec.fee_structure_id
            ):
                raise ValidationError(
                    'Selected payment plan must belong to the '
                    'application\'s fee structure.'
                )

    # ═════════════════════════════════════════════════════════════════════════
    # Onchange
    # ═════════════════════════════════════════════════════════════════════════
    @api.onchange('admission_register_id')
    def _onchange_admission_register(self):
        """Auto-populate fields from register."""
        reg = self.admission_register_id
        if reg:
            self.program_id = reg.program_id
            self.batch_id = reg.batch_id
            self.academic_year_id = reg.academic_year_id
            self.fee_structure_id = reg.fee_structure_id
            self.available_payment_plan_ids = [
                (6, 0, reg.available_payment_plan_ids.ids)
            ]
            self.selected_payment_plan_id = reg.default_payment_plan_id
        else:
            self.available_payment_plan_ids = [(5, 0, 0)]
            self.selected_payment_plan_id = False

    @api.onchange('program_id', 'academic_year_id', 'batch_id')
    def _onchange_academic_scope(self):
        """Clear batch if it no longer matches."""
        if self.batch_id and (
            self.batch_id.program_id != self.program_id
            or self.batch_id.academic_year_id != self.academic_year_id
        ):
            self.batch_id = False

    @api.onchange('fee_structure_id')
    def _onchange_fee_structure(self):
        """Load available payment plans from the fee structure."""
        plans = self._get_available_payment_plans()
        self.available_payment_plan_ids = [(6, 0, plans.ids)]
        if self.selected_payment_plan_id and \
                self.selected_payment_plan_id not in plans:
            self.selected_payment_plan_id = False

    # ═════════════════════════════════════════════════════════════════════════
    # Populate from Register
    # ═════════════════════════════════════════════════════════════════════════
    def _populate_from_register(self):
        """Fill academic and fee context from the linked admission register."""
        self.ensure_one()
        reg = self.admission_register_id
        if not reg:
            return
        vals = {}
        if not self.program_id and reg.program_id:
            vals['program_id'] = reg.program_id.id
        if not self.batch_id and reg.batch_id:
            vals['batch_id'] = reg.batch_id.id
        if not self.academic_year_id and reg.academic_year_id:
            vals['academic_year_id'] = reg.academic_year_id.id
        if not self.fee_structure_id and reg.fee_structure_id:
            vals['fee_structure_id'] = reg.fee_structure_id.id
        if reg.available_payment_plan_ids:
            vals['available_payment_plan_ids'] = [
                (6, 0, reg.available_payment_plan_ids.ids)
            ]
        if not self.selected_payment_plan_id and reg.default_payment_plan_id:
            vals['selected_payment_plan_id'] = reg.default_payment_plan_id.id
        if vals:
            self.write(vals)

    # ═════════════════════════════════════════════════════════════════════════
    # Fee Resolution
    # ═════════════════════════════════════════════════════════════════════════
    def _resolve_fee_structure(self):
        """
        Resolve fee structure for this application's scope.
        Same batch → program fallback as register.
        """
        self.ensure_one()
        FeeStructure = self.env['edu.fee.structure']
        if self.batch_id:
            structure = FeeStructure.search([
                ('program_id', '=', self.program_id.id),
                ('academic_year_id', '=', self.academic_year_id.id),
                ('batch_id', '=', self.batch_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if structure:
                return structure
        structure = FeeStructure.search([
            ('program_id', '=', self.program_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('batch_id', '=', False),
            ('state', '=', 'active'),
        ], limit=1)
        return structure or FeeStructure

    def _get_available_payment_plans(self):
        """Return payment plans from fee structure."""
        self.ensure_one()
        if self.fee_structure_id:
            return self.fee_structure_id.payment_plan_ids
        return self.env['edu.fee.payment.plan']

    # ═════════════════════════════════════════════════════════════════════════
    # Fee Preview Computeds
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends('fee_structure_id', 'fee_structure_id.total_amount',
                 'fee_structure_id.line_ids.amount',
                 'fee_structure_id.line_ids.scholarship_allowed')
    def _compute_fee_preview(self):
        for rec in self:
            if rec.fee_structure_id:
                rec.base_total_fee = rec.fee_structure_id.total_amount
                rec.scholarship_eligible_total = (
                    rec.fee_structure_id.get_scholarship_applicable_total()
                )
            else:
                rec.base_total_fee = 0.0
                rec.scholarship_eligible_total = 0.0

    def _compute_fee_summary_display(self):
        """Render a human-readable fee summary for the form view."""
        for rec in self:
            if not rec.fee_structure_id:
                rec.fee_summary_display = 'No fee structure assigned.'
                continue
            summary = rec.fee_structure_id.get_fee_summary()
            lines = []
            for bucket in summary:
                lines.append(
                    f"--- {bucket['program_term_name']} "
                    f"(Stage {bucket['progression_no']}) ---"
                )
                for fl in bucket['lines']:
                    sch_flag = ' [S]' if fl['scholarship_allowed'] else ''
                    lines.append(f"  {fl['fee_head']}: {fl['amount']:,.2f}{sch_flag}")
                lines.append(f"  Subtotal: {bucket['subtotal']:,.2f}")
            lines.append(f"\nTotal: {rec.base_total_fee:,.2f}")
            lines.append(
                f"Scholarship-Eligible: {rec.scholarship_eligible_total:,.2f}"
            )
            rec.fee_summary_display = '\n'.join(lines)

    # ═════════════════════════════════════════════════════════════════════════
    # Scholarship Summary Computation
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends(
        'scholarship_review_ids.state',
        'scholarship_review_ids.calculated_discount_amount',
        'scholarship_review_ids.cap_applied',
        'scholarship_eligible_total',
    )
    def _compute_scholarship_summary(self):
        for rec in self:
            approved_lines = rec.scholarship_review_ids.filtered(
                lambda r: r.state == 'approved'
            )
            if not approved_lines:
                has_any = bool(rec.scholarship_review_ids)
                all_rejected = has_any and all(
                    r.state == 'rejected'
                    for r in rec.scholarship_review_ids
                )
                rec.total_scholarship_discount_amount = 0.0
                rec.net_fee_after_scholarship = rec.base_total_fee
                rec.scholarship_cap_applied = False
                rec.scholarship_note_summary = False
                if all_rejected:
                    rec.scholarship_status = 'rejected'
                elif has_any:
                    rec.scholarship_status = 'pending'
                else:
                    rec.scholarship_status = 'not_applicable'
                continue

            # Calculate total discount from approved lines
            total_discount = sum(
                approved_lines.mapped('calculated_discount_amount')
            )
            eligible = rec.scholarship_eligible_total or 0.0

            # Final cap: never exceed eligible amount
            cap_applied = False
            if float_compare(total_discount, eligible, precision_digits=2) > 0:
                total_discount = eligible
                cap_applied = True

            # Floor at zero
            if float_compare(total_discount, 0.0, precision_digits=2) < 0:
                total_discount = 0.0

            total_discount = float_round(total_discount, precision_digits=2)
            net = float_round(
                rec.base_total_fee - total_discount, precision_digits=2
            )
            if float_compare(net, 0.0, precision_digits=2) < 0:
                net = 0.0

            # Determine status
            any_pending = any(
                r.state in ('draft', 'under_review')
                for r in rec.scholarship_review_ids
            )
            any_rejected = any(
                r.state == 'rejected' for r in rec.scholarship_review_ids
            )
            if any_pending:
                status = 'pending'
            elif any_rejected and approved_lines:
                status = 'partially_approved'
            else:
                status = 'approved'

            # Check if any individual line had a cap applied
            line_cap = any(approved_lines.mapped('cap_applied'))

            # Build summary notes
            notes = []
            for line in approved_lines.sorted('sequence'):
                notes.append(
                    f"{line.scholarship_scheme_id.name}: "
                    f"{line.calculated_discount_amount:,.2f}"
                )
            if cap_applied:
                notes.append(
                    f"[Total capped to scholarship-eligible amount: "
                    f"{eligible:,.2f}]"
                )

            rec.total_scholarship_discount_amount = total_discount
            rec.net_fee_after_scholarship = net
            rec.scholarship_cap_applied = cap_applied or line_cap
            rec.scholarship_status = status
            rec.scholarship_note_summary = '\n'.join(notes) if notes else False

    def _compute_scholarship_review_count(self):
        for rec in self:
            reviews = rec.scholarship_review_ids
            rec.scholarship_review_count = len(reviews)
            rec.approved_scholarship_count = len(
                reviews.filtered(lambda r: r.state == 'approved')
            )

    # ═════════════════════════════════════════════════════════════════════════
    # Process Flags
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_process_flags(self):
        for rec in self:
            rec.can_generate_offer = (
                rec.state in ('under_review', 'scholarship_review')
                and rec.review_complete
                and rec.fee_structure_id
            )
            rec.can_accept_offer = (
                rec.state == 'offered'
                and rec.offer_status == 'sent'
            )
            rec.can_mark_ready_for_enrollment = (
                rec.state == 'offer_accepted'
                and rec.fee_confirmed
                and rec.selected_payment_plan_id
            )
            rec.can_enroll = rec.state == 'ready_for_enrollment'

    def _compute_enrollment_readiness(self):
        for rec in self:
            blocks = []
            if rec.state != 'offer_accepted':
                blocks.append('Offer must be accepted.')
            if not rec.fee_confirmed:
                blocks.append('Fee must be confirmed.')
            if not rec.selected_payment_plan_id:
                blocks.append('A payment plan must be selected.')
            rec.enrollment_ready = not blocks
            rec.enrollment_block_reason = '\n'.join(blocks) if blocks else False

    # ═════════════════════════════════════════════════════════════════════════
    # State Transitions
    # ═════════════════════════════════════════════════════════════════════════
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    f'Application "{rec.application_no}" is not in draft state.'
                )
            if not rec.applicant_profile_id:
                raise UserError('Applicant profile is required before submission.')
            if not rec.program_id:
                raise UserError('Program is required before submission.')
        self.write({'state': 'submitted'})

    def action_start_review(self):
        self.filtered(
            lambda r: r.state == 'submitted'
        ).write({'state': 'under_review'})

    def action_start_scholarship_review(self):
        """Move to scholarship review state."""
        for rec in self:
            if rec.state not in ('under_review',):
                raise UserError(
                    f'Application "{rec.application_no}" must be under review '
                    'to start scholarship review.'
                )
        self.write({'state': 'scholarship_review'})

    def action_mark_review_complete(self):
        self.write({'review_complete': True})

    def action_generate_offer(self):
        """Generate offer letter and transition to offered state."""
        for rec in self:
            if not rec.can_generate_offer:
                raise UserError(
                    f'Cannot generate offer for "{rec.application_no}". '
                    'Ensure review is complete and a fee structure is assigned.'
                )
            # Validate scholarship finalization if reviews exist
            pending = rec.scholarship_review_ids.filtered(
                lambda r: r.state in ('draft', 'under_review')
            )
            if pending:
                raise UserError(
                    f'Application "{rec.application_no}" has {len(pending)} '
                    'pending scholarship review(s). Finalize them first.'
                )
            # Recompute scholarship summary before offer
            rec._recompute_scholarship_summary()

        self.write({
            'state': 'offered',
            'offer_status': 'sent',
            'offer_letter_generated': True,
            'offer_letter_date': fields.Date.today(),
        })

    def action_accept_offer(self):
        """Accept the offer — triggers fee confirmation and freezes outcomes."""
        for rec in self:
            if not rec.can_accept_offer:
                raise UserError(
                    f'Cannot accept offer for "{rec.application_no}". '
                    'Offer must be in "sent" status.'
                )
        now = fields.Datetime.now()
        self.write({
            'state': 'offer_accepted',
            'offer_status': 'accepted',
            'offer_acceptance_date': now,
            'fee_confirmed': True,
            'fee_confirmation_date': now,
        })

    def action_reject_offer(self):
        for rec in self:
            if rec.state != 'offered':
                raise UserError(
                    f'Application "{rec.application_no}" is not in offered state.'
                )
        self.write({
            'state': 'offer_rejected',
            'offer_status': 'rejected',
        })

    def action_mark_ready_for_enrollment(self):
        """Verify enrollment readiness and transition state."""
        for rec in self:
            if not rec.can_mark_ready_for_enrollment:
                blocks = rec.enrollment_block_reason or 'Unknown issue.'
                raise UserError(
                    f'Cannot mark "{rec.application_no}" ready for enrollment:\n'
                    f'{blocks}'
                )
        self.write({'state': 'ready_for_enrollment'})

    def action_enroll(self):
        """
        Enrollment hook — creates enrollment record if enrollment module
        is installed, otherwise marks as enrolled.
        """
        for rec in self:
            if rec.state != 'ready_for_enrollment':
                raise UserError(
                    f'Application "{rec.application_no}" is not ready '
                    'for enrollment.'
                )
        # Check if enrollment module exists
        enrollment_model = self.env.get('edu.enrollment')
        if enrollment_model is not None:
            for rec in self:
                vals = rec._prepare_enrollment_vals()
                enrollment_model.create(vals)
        self.write({'state': 'enrolled'})

    def action_cancel(self):
        for rec in self:
            if rec.state in ('enrolled',):
                raise UserError(
                    f'Cannot cancel enrolled application "{rec.application_no}".'
                )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ('cancelled', 'submitted'):
                raise UserError(
                    f'Can only reset to draft from cancelled or submitted state '
                    f'(application: "{rec.application_no}").'
                )
        self.write({
            'state': 'draft',
            'review_complete': False,
            'offer_status': 'not_generated',
            'offer_letter_generated': False,
            'offer_letter_date': False,
            'offer_letter_ref': False,
            'offer_acceptance_date': False,
            'fee_confirmed': False,
            'fee_confirmation_date': False,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Scholarship Calculation Engine
    # ═════════════════════════════════════════════════════════════════════════
    def _recompute_scholarship_summary(self):
        """
        Recalculate all approved scholarship review lines with proper
        stacking, capping, and conflict validation.
        """
        self.ensure_one()
        approved = self.scholarship_review_ids.filtered(
            lambda r: r.state == 'approved'
        ).sorted('sequence')
        if not approved:
            return

        # Validate stacking rules
        self._validate_scholarship_stacking(approved)

        # Apply caps to individual lines
        eligible = self.scholarship_eligible_total or 0.0
        running_total = 0.0

        for line in approved:
            raw = line._calculate_raw_discount(eligible)
            capped = self._apply_scholarship_caps(line, raw, eligible)

            # Ensure running total doesn't exceed eligible
            if float_compare(
                running_total + capped, eligible, precision_digits=2
            ) > 0:
                capped = max(0.0, eligible - running_total)
                line.cap_applied = True

            line.calculated_discount_amount = float_round(
                capped, precision_digits=2
            )
            running_total += capped

    def _validate_scholarship_stacking(self, approved_lines):
        """
        Validate stacking rules across all approved scholarship lines.

        Rules:
        1. Exclusive scholarship cannot coexist with any other
        2. Non-stackable schemes cannot combine with others
        3. Schemes in the same stacking group may conflict
        """
        if len(approved_lines) <= 1:
            return

        exclusive = approved_lines.filtered(
            lambda r: r.exclusive_snapshot
        )
        if exclusive:
            raise UserError(
                f'Scholarship "{exclusive[0].scholarship_scheme_id.name}" '
                'is exclusive and cannot be combined with other scholarships. '
                f'Found {len(approved_lines)} approved lines total.'
            )

        non_stackable = approved_lines.filtered(
            lambda r: not r.stacking_allowed_snapshot
        )
        if non_stackable and len(approved_lines) > 1:
            names = ', '.join(
                non_stackable.mapped('scholarship_scheme_id.name')
            )
            raise UserError(
                f'Scholarship(s) [{names}] do not allow stacking, '
                'but multiple scholarships are approved.'
            )

    def _apply_scholarship_caps(self, review_line, raw_amount, eligible_total):
        """
        Apply scheme-level caps to a single scholarship review line.

        Returns the capped amount.
        """
        amount = raw_amount
        cap_applied = False
        scheme = review_line.scholarship_scheme_id

        # Scheme max percent cap
        if (
            scheme.max_discount_percent > 0
            and eligible_total > 0
        ):
            max_by_percent = eligible_total * scheme.max_discount_percent / 100.0
            if float_compare(amount, max_by_percent, precision_digits=2) > 0:
                amount = max_by_percent
                cap_applied = True

        # Scheme max amount cap
        if scheme.max_discount_amount > 0:
            if float_compare(
                amount, scheme.max_discount_amount, precision_digits=2
            ) > 0:
                amount = scheme.max_discount_amount
                cap_applied = True

        # Never negative
        if float_compare(amount, 0.0, precision_digits=2) < 0:
            amount = 0.0

        review_line.cap_applied = cap_applied
        return amount

    # ═════════════════════════════════════════════════════════════════════════
    # Offer Letter Context
    # ═════════════════════════════════════════════════════════════════════════
    def _prepare_offer_letter_context(self):
        """
        Returns context dict for the offer letter report template.
        """
        self.ensure_one()
        profile = self.applicant_profile_id
        return {
            'application': self,
            'applicant_name': profile.full_name,
            'program_name': self.program_id.name,
            'batch_name': self.batch_id.name if self.batch_id else '',
            'academic_year': self.academic_year_id.name if self.academic_year_id else '',
            'fee_summary': (
                self.fee_structure_id.get_fee_summary()
                if self.fee_structure_id else []
            ),
            'base_total_fee': self.base_total_fee,
            'scholarship_discount': self.total_scholarship_discount_amount,
            'net_fee': self.net_fee_after_scholarship,
            'payment_plan': (
                self.selected_payment_plan_id.name
                if self.selected_payment_plan_id else 'Not selected'
            ),
            'offer_date': self.offer_letter_date,
            'expiry_date': self.offer_expiry_date,
            'scholarship_details': [
                {
                    'scheme': r.scholarship_scheme_id.name,
                    'amount': r.calculated_discount_amount,
                    'type': r.approved_type,
                }
                for r in self.scholarship_review_ids.filtered(
                    lambda r: r.state == 'approved'
                )
            ],
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Enrollment Handoff
    # ═════════════════════════════════════════════════════════════════════════
    def _check_enrollment_ready(self):
        """Raise UserError if not ready for enrollment."""
        self.ensure_one()
        if not self.enrollment_ready:
            raise UserError(
                f'Application "{self.application_no}" is not ready for enrollment.\n'
                f'{self.enrollment_block_reason}'
            )

    def _prepare_enrollment_vals(self):
        """
        Prepare values dict for creating enrollment record.
        Future enrollment module should consume this.
        """
        self.ensure_one()
        self._check_enrollment_ready()
        return {
            'applicant_profile_id': self.applicant_profile_id.id,
            'partner_id': self.partner_id.id,
            'crm_lead_id': self.crm_lead_id.id if self.crm_lead_id else False,
            'admission_application_id': self.id,
            'program_id': self.program_id.id,
            'batch_id': self.batch_id.id if self.batch_id else False,
            'academic_year_id': (
                self.academic_year_id.id if self.academic_year_id else False
            ),
            'department_id': self.department_id.id if self.department_id else False,
            'fee_structure_id': (
                self.fee_structure_id.id if self.fee_structure_id else False
            ),
            'selected_payment_plan_id': (
                self.selected_payment_plan_id.id
                if self.selected_payment_plan_id else False
            ),
            'total_scholarship_discount_amount': (
                self.total_scholarship_discount_amount
            ),
            'net_fee_after_scholarship': self.net_fee_after_scholarship,
            'offer_acceptance_date': self.offer_acceptance_date,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_scholarship_reviews(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Scholarship Reviews — {self.application_no}',
            'res_model': 'edu.admission.scholarship.review',
            'view_mode': 'list,form',
            'domain': [('application_id', '=', self.id)],
            'context': {'default_application_id': self.id},
        }

    def action_view_applicant_profile(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Applicant Profile',
            'res_model': 'edu.applicant.profile',
            'res_id': self.applicant_profile_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_recompute_scholarship(self):
        """Manual trigger for scholarship recalculation."""
        for rec in self:
            if rec.state in self._FROZEN_STATES:
                raise UserError(
                    f'Cannot recompute scholarships on "{rec.application_no}" — '
                    'the application is frozen.'
                )
            rec._recompute_scholarship_summary()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Scholarship Recalculated',
                'message': 'Scholarship summary has been recalculated.',
                'type': 'success',
                'sticky': False,
            },
        }
