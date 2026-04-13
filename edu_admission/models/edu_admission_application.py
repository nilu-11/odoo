import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round

_logger = logging.getLogger(__name__)


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
        default=lambda self: self.env['edu.academic.year']._get_current_year(),
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
    fee_summary_display = fields.Html(
        string='Fee Summary',
        compute='_compute_fee_summary_display',
        sanitize=False,
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
            ('not_applicable',   'Not Applicable'),
            ('pending',          'Pending'),
            ('under_review',     'Under Review'),
            ('approved',         'Approved'),
            ('partially_approved', 'Partially Approved'),
            ('rejected',         'Rejected'),
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
    scholarship_scheme_count = fields.Integer(
        string='Distinct Schemes',
        compute='_compute_scholarship_review_count',
    )
    scholarship_cap_reason_summary = fields.Text(
        string='Cap Reason Summary',
        compute='_compute_scholarship_summary',
        store=True,
        help='Aggregated explanation of all caps applied across approved review lines.',
    )
    scholarship_freeze_date = fields.Datetime(
        string='Scholarship Frozen On',
        readonly=True,
        copy=False,
        help='Timestamp when the scholarship outcome was frozen (at offer acceptance).',
    )
    scholarship_frozen = fields.Boolean(
        string='Scholarship Frozen',
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
        help='Once True, approved scholarship review lines cannot be edited.',
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
            # Fallback: if still no fee structure, try direct resolution from
            # program/year/batch (e.g. when created from CRM lead without a
            # matching open register).
            if not rec.fee_structure_id and rec.program_id and rec.academic_year_id:
                structure = rec._resolve_fee_structure()
                if structure:
                    vals_update = {'fee_structure_id': structure.id}
                    if structure.payment_plan_ids:
                        vals_update['available_payment_plan_ids'] = [
                            (6, 0, structure.payment_plan_ids.ids)
                        ]
                        if not rec.selected_payment_plan_id:
                            vals_update['selected_payment_plan_id'] = (
                                structure.payment_plan_ids[0].id
                            )
                    rec.write(vals_update)
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
            # Once the fee is confirmed (offer accepted), the snapshot is frozen.
            # Do not recompute — protects against fee structure edits after acceptance.
            if rec.fee_confirmed:
                continue
            if rec.fee_structure_id:
                rec.base_total_fee = rec.fee_structure_id.total_amount
                rec.scholarship_eligible_total = (
                    rec.fee_structure_id.get_scholarship_applicable_total()
                )
            else:
                rec.base_total_fee = 0.0
                rec.scholarship_eligible_total = 0.0

    def _compute_fee_summary_display(self):
        """Render a tabular fee summary for the form view.

        Rows = program terms (semesters/stages), columns = fee heads,
        cells = amounts. Scholarship info is shown below the table.
        """
        from markupsafe import Markup
        for rec in self:
            if not rec.fee_structure_id:
                rec.fee_summary_display = Markup(
                    '<p class="text-muted">No fee structure assigned.</p>'
                )
                continue
            summary = rec.fee_structure_id.get_fee_summary()
            if not summary:
                rec.fee_summary_display = Markup(
                    '<p class="text-muted">No fee lines configured.</p>'
                )
                continue

            # Collect unique fee heads across all terms, preserving
            # first-seen order (typically matches sequence within terms).
            head_order = []
            seen_heads = set()
            for bucket in summary:
                for fl in bucket['lines']:
                    key = fl['fee_head']
                    if key not in seen_heads:
                        seen_heads.add(key)
                        head_order.append({
                            'name': fl['fee_head'],
                            'scholarship_allowed': fl['scholarship_allowed'],
                        })

            def _fmt(amount):
                return f'{amount:,.2f}'

            rows_html = []
            column_totals = {h['name']: 0.0 for h in head_order}
            for bucket in summary:
                # Map head_name -> amount for this term
                line_map = {fl['fee_head']: fl['amount'] for fl in bucket['lines']}
                cells = []
                for h in head_order:
                    amt = line_map.get(h['name'], 0.0)
                    column_totals[h['name']] += amt
                    cells.append(
                        f'<td class="text-end">{_fmt(amt) if amt else "—"}</td>'
                    )
                rows_html.append(
                    '<tr>'
                    f'<td><strong>{bucket["program_term_name"]}</strong>'
                    f'<br/><small class="text-muted">Stage '
                    f'{bucket["progression_no"]} · {bucket["academic_year"]}</small></td>'
                    + ''.join(cells)
                    + f'<td class="text-end"><strong>{_fmt(bucket["subtotal"])}</strong></td>'
                    '</tr>'
                )

            # Totals row
            total_cells = ''.join(
                f'<td class="text-end"><strong>{_fmt(column_totals[h["name"]])}</strong></td>'
                for h in head_order
            )
            totals_row = (
                '<tr class="table-active">'
                '<td><strong>Total</strong></td>'
                + total_cells
                + f'<td class="text-end"><strong>{_fmt(rec.base_total_fee)}</strong></td>'
                '</tr>'
            )

            # Header row
            head_cells = ''.join(
                f'<th class="text-end">{h["name"]}'
                + (' <small>(S)</small>' if h['scholarship_allowed'] else '')
                + '</th>'
                for h in head_order
            )
            header = (
                '<thead><tr>'
                '<th>Term / Stage</th>'
                + head_cells
                + '<th class="text-end">Subtotal</th>'
                '</tr></thead>'
            )

            table_html = (
                '<div class="table-responsive">'
                '<table class="table table-sm table-bordered">'
                + header
                + '<tbody>'
                + ''.join(rows_html)
                + totals_row
                + '</tbody></table></div>'
            )

            # Scholarship section
            scholarship_parts = [
                f'<div class="mt-2"><strong>Scholarship-Eligible Total:</strong> '
                f'{_fmt(rec.scholarship_eligible_total)}</div>'
            ]
            if rec.total_scholarship_discount_amount:
                scholarship_parts.append(
                    f'<div><strong>Scholarship Discount:</strong> '
                    f'− {_fmt(rec.total_scholarship_discount_amount)}</div>'
                )
                scholarship_parts.append(
                    f'<div><strong>Net Fee After Scholarship:</strong> '
                    f'{_fmt(rec.net_fee_after_scholarship)}</div>'
                )
            if rec.scholarship_note_summary:
                note_html = rec.scholarship_note_summary.replace('\n', '<br/>')
                scholarship_parts.append(
                    f'<div class="mt-2"><small class="text-muted">'
                    f'{note_html}</small></div>'
                )
            if head_order and any(h['scholarship_allowed'] for h in head_order):
                scholarship_parts.append(
                    '<div class="mt-1"><small class="text-muted">'
                    '(S) = Scholarship-eligible fee head</small></div>'
                )

            rec.fee_summary_display = Markup(
                table_html + ''.join(scholarship_parts)
            )

    # ═════════════════════════════════════════════════════════════════════════
    # Scholarship Summary Computation
    # ═════════════════════════════════════════════════════════════════════════
    @api.depends(
        'scholarship_review_ids.state',
        'scholarship_review_ids.calculated_discount_amount',
        'scholarship_review_ids.cap_applied',
        'scholarship_review_ids.cap_reason',
        'scholarship_eligible_total',
    )
    def _compute_scholarship_summary(self):
        """
        Aggregate approved scholarship review lines into application-level
        scholarship summary fields.

        Reads already-calculated per-line discount amounts (set by
        _recompute_scholarship_summary) and applies the final global cap.
        Does NOT re-run per-line cap/stacking logic — that belongs in
        _recompute_scholarship_summary.
        """
        for rec in self:
            all_reviews = rec.scholarship_review_ids
            approved_lines = all_reviews.filtered(lambda r: r.state == 'approved')

            if not approved_lines:
                has_any = bool(all_reviews)
                all_rejected = has_any and all(
                    r.state in ('rejected', 'cancelled') for r in all_reviews
                )
                any_active_review = any(
                    r.state in ('under_review', 'recommended') for r in all_reviews
                )
                rec.total_scholarship_discount_amount = 0.0
                rec.net_fee_after_scholarship = rec.base_total_fee
                rec.scholarship_cap_applied = False
                rec.scholarship_note_summary = False
                rec.scholarship_cap_reason_summary = False
                if all_rejected:
                    rec.scholarship_status = 'rejected'
                elif any_active_review:
                    rec.scholarship_status = 'under_review'
                elif has_any:
                    rec.scholarship_status = 'pending'
                else:
                    rec.scholarship_status = 'not_applicable'
                continue

            # Sum per-line calculated discounts (caps already applied per-line)
            total_discount = sum(
                l.calculated_discount_amount for l in approved_lines
            )
            eligible = rec.scholarship_eligible_total or 0.0

            # Global cap: total discount can never exceed eligible amount
            global_cap_applied = False
            global_cap_reason = False
            if float_compare(total_discount, eligible, precision_digits=2) > 0:
                total_discount = eligible
                global_cap_applied = True
                global_cap_reason = (
                    f'Total discount capped to scholarship-eligible amount '
                    f'({eligible:,.2f})'
                )

            # Floor at zero
            if float_compare(total_discount, 0.0, precision_digits=2) < 0:
                total_discount = 0.0

            total_discount = float_round(total_discount, precision_digits=2)
            net = float_round(rec.base_total_fee - total_discount, precision_digits=2)
            if float_compare(net, 0.0, precision_digits=2) < 0:
                net = 0.0

            # Status determination
            any_pending = any(
                r.state in ('draft', 'under_review', 'recommended')
                for r in all_reviews
            )
            any_rejected = any(r.state == 'rejected' for r in all_reviews)
            if any_pending:
                status = 'under_review' if any(
                    r.state in ('under_review', 'recommended') for r in all_reviews
                ) else 'pending'
            elif any_rejected and approved_lines:
                status = 'partially_approved'
            else:
                status = 'approved'

            # Aggregate line-level cap flags and reasons
            line_cap = any(l.cap_applied for l in approved_lines)
            cap_reasons = [
                f'{l.scholarship_scheme_id.name}: {l.cap_reason}'
                for l in approved_lines
                if l.cap_applied and l.cap_reason
            ]
            if global_cap_reason:
                cap_reasons.append(global_cap_reason)

            # Build human-readable summary notes
            notes = []
            for line in approved_lines.sorted('sequence'):
                cap_flag = ' [capped]' if line.cap_applied else ''
                notes.append(
                    f'{line.scholarship_scheme_id.name}'
                    f' ({line.scheme_category_snapshot or line.scholarship_scheme_id.eligibility_basis})'
                    f': {line.calculated_discount_amount:,.2f}{cap_flag}'
                )
            if global_cap_reason:
                notes.append(f'[{global_cap_reason}]')

            rec.total_scholarship_discount_amount = total_discount
            rec.net_fee_after_scholarship = net
            rec.scholarship_cap_applied = global_cap_applied or line_cap
            rec.scholarship_status = status
            rec.scholarship_note_summary = '\n'.join(notes) if notes else False
            rec.scholarship_cap_reason_summary = (
                '\n'.join(cap_reasons) if cap_reasons else False
            )

    def _compute_scholarship_review_count(self):
        for rec in self:
            reviews = rec.scholarship_review_ids
            rec.scholarship_review_count = len(reviews)
            rec.approved_scholarship_count = len(
                reviews.filtered(lambda r: r.state == 'approved')
            )
            rec.scholarship_scheme_count = len(
                reviews.mapped('scholarship_scheme_id')
            )

    # ═════════════════════════════════════════════════════════════════════════
    # Process Flags
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_process_flags(self):
        for rec in self:
            rec.can_generate_offer = (
                rec.state in ('under_review', 'scholarship_review')
                and rec.review_complete
                and bool(rec.fee_structure_id)
            )
            rec.can_accept_offer = (
                rec.state == 'offered'
                and rec.offer_status == 'sent'
            )
            # All readiness criteria must pass before "Ready for Enrollment"
            rec.can_mark_ready_for_enrollment = (
                rec.state == 'offer_accepted'
                and not rec._get_enrollment_block_reasons()
            )
            # can_enroll: application is ready_for_enrollment
            # (the enrollment extension overrides this to also check
            #  enrollment_count == 0, preventing duplicate creation)
            rec.can_enroll = rec.state == 'ready_for_enrollment'

    @api.depends(
        'state', 'offer_status', 'fee_confirmed', 'selected_payment_plan_id',
        'applicant_profile_id', 'program_id', 'batch_id', 'academic_year_id',
        'fee_structure_id', 'batch_id.current_program_term_id',
    )
    def _compute_enrollment_readiness(self):
        """
        Compute enrollment_ready and enrollment_block_reason based on a
        comprehensive check of all fields required for handoff to edu_enrollment.
        """
        for rec in self:
            blocks = rec._get_enrollment_block_reasons()
            rec.enrollment_ready = not blocks
            rec.enrollment_block_reason = (
                '\n'.join(f'• {b}' for b in blocks) if blocks else False
            )

    def _get_enrollment_block_reasons(self):
        """
        Return a list of human-readable reasons blocking enrollment creation.
        An empty list means the application is fully ready for enrollment.

        Checks mirror edu.enrollment._check_application_enrollment_readiness()
        so that the application can self-validate before calling the enrollment
        module.
        """
        self.ensure_one()
        blocks = []

        # Hard stops — no point checking further
        if self.state in ('cancelled', 'offer_rejected'):
            blocks.append(f'Application is in "{self.state}" state.')
            return blocks

        # Offer outcome
        if self.offer_status != 'accepted':
            blocks.append(
                f'Offer is not accepted (current: "{self.offer_status}").'
            )

        # Fee confirmation
        if not self.fee_confirmed:
            blocks.append('Fee is not confirmed.')

        # Payment plan
        if not self.selected_payment_plan_id:
            blocks.append('No payment plan selected.')

        # Identity
        if not self.applicant_profile_id:
            blocks.append('Applicant profile is missing.')

        # Academic placement
        if not self.program_id:
            blocks.append('Program is missing.')
        if not self.batch_id:
            blocks.append('Batch is missing.')
        if not self.academic_year_id:
            blocks.append('Academic year is missing.')

        # Fee structure
        if not self.fee_structure_id:
            blocks.append('Fee structure is missing.')

        # Batch must have a current program term (enrollment requires it)
        if self.batch_id and not self.batch_id.current_program_term_id:
            blocks.append(
                f'Batch "{self.batch_id.name}" has no current program term '
                'configured. Set the current progression stage on the batch.'
            )

        return blocks

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
        """Accept the offer — confirms fees and freezes scholarship outcome."""
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
        # Freeze scholarship outcome immediately upon offer acceptance
        for rec in self:
            rec.action_freeze_scholarship_outcome()

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
        """
        Validate full enrollment readiness and transition to ready_for_enrollment.

        All downstream requirements (fee, batch term, payment plan, etc.) are
        checked here via _get_enrollment_block_reasons() so that the enrollment
        module can accept the application immediately upon creation.
        """
        for rec in self:
            if rec.state != 'offer_accepted':
                raise UserError(
                    f'Application "{rec.application_no}" must be in '
                    '"offer_accepted" state to mark ready for enrollment.'
                )
            blocks = rec._get_enrollment_block_reasons()
            if blocks:
                raise UserError(
                    f'Cannot mark "{rec.application_no}" ready for enrollment:\n'
                    + '\n'.join(f'  • {b}' for b in blocks)
                )
        self.write({'state': 'ready_for_enrollment'})

    def action_enroll(self):
        """
        Enrollment hook — base implementation for when edu_enrollment is not
        installed.

        When edu_enrollment IS installed, this method is fully overridden by
        edu_enrollment's application extension (edu_enrollment/models/
        edu_admission_application.py) which properly creates the enrollment
        record, handles duplicates, and returns a form view action.

        Base behaviour (standalone admission without enrollment module):
        - Validates state and readiness
        - If enrollment module is present, delegates to it
        - Advances application state to 'enrolled'
        """
        for rec in self:
            if rec.state != 'ready_for_enrollment':
                raise UserError(
                    f'Application "{rec.application_no}" is not ready '
                    'for enrollment. Use "Mark Ready for Enrollment" first.'
                )
            blocks = rec._get_enrollment_block_reasons()
            if blocks:
                raise UserError(
                    f'Cannot enroll "{rec.application_no}":\n'
                    + '\n'.join(f'  • {b}' for b in blocks)
                )
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

    def _get_approved_scholarship_lines(self):
        """
        Return all approved scholarship review lines for this application.
        Excludes cancelled and rejected lines.
        """
        self.ensure_one()
        return self.scholarship_review_ids.filtered(
            lambda r: r.state == 'approved'
        )

    def _get_sorted_scholarship_lines(self, approved_lines=None):
        """
        Return approved lines sorted by sequence (priority) ascending.

        Lower sequence = higher priority = calculated first.
        Within the same sequence, percentage/full awards come before fixed/custom
        so percentage-based awards are applied to the full eligible base first.
        """
        if approved_lines is None:
            approved_lines = self._get_approved_scholarship_lines()

        def _sort_key(line):
            type_order = {
                'full': 0,
                'percentage': 1,
                'fixed': 2,
                'custom': 3,
            }
            t = type_order.get(line.approved_type or 'custom', 3)
            return (line.sequence, t, line.id)

        return approved_lines.sorted(key=_sort_key)

    def _validate_scholarship_stacking(self, approved_lines):
        """
        Validate stacking rules across all approved scholarship lines.

        Rules enforced:
        1. Exclusive scholarship cannot coexist with any other approved line
        2. Non-stackable scheme cannot coexist with any other approved line
        3. Only one scheme per stacking group is allowed (same-group conflict)

        Uses snapshot values so that the validation reflects the rules
        that were in force when each line was approved.
        """
        if len(approved_lines) <= 1:
            return

        # Rule 1: exclusive
        exclusive = approved_lines.filtered(lambda r: r.exclusive_snapshot)
        if exclusive:
            names = ', '.join(exclusive.mapped('scholarship_scheme_id.name'))
            raise UserError(
                f'Scholarship(s) [{names}] are exclusive and cannot be '
                'combined with any other scholarship. '
                f'Found {len(approved_lines)} approved lines total.'
            )

        # Rule 2: non-stackable
        non_stackable = approved_lines.filtered(
            lambda r: not r.stacking_allowed_snapshot
        )
        if non_stackable:
            names = ', '.join(
                non_stackable.mapped('scholarship_scheme_id.name')
            )
            raise UserError(
                f'Scholarship(s) [{names}] do not allow stacking, '
                'but multiple scholarships are approved on this application.'
            )

        # Rule 3: stacking-group conflict — only one per group
        group_seen = {}
        for line in approved_lines:
            grp = line.stacking_group_snapshot
            if not grp:
                continue
            if grp in group_seen:
                raise UserError(
                    f'Two scholarships from the same stacking group '
                    f'"{grp}" are approved: '
                    f'"{group_seen[grp]}" and '
                    f'"{line.scholarship_scheme_id.name}". '
                    'Only one scholarship per stacking group is allowed.'
                )
            group_seen[grp] = line.scholarship_scheme_id.name

    def _apply_scheme_caps(self, review_line, raw_amount, eligible_total):
        """
        Apply scheme-level caps (percent cap + amount cap) to a single
        scholarship review line.  Uses snapshot values for deterministic
        historical results.

        Returns: (capped_amount: float, cap_applied: bool, cap_reason: str|False)
        """
        amount = raw_amount
        cap_applied = False
        cap_reasons = []

        # Use snapshots for scheme caps (not live scheme values)
        max_pct = review_line.max_discount_percent_snapshot
        max_amt = review_line.max_discount_amount_snapshot

        if max_pct > 0 and eligible_total > 0:
            max_by_pct = float_round(
                eligible_total * max_pct / 100.0, precision_digits=2
            )
            if float_compare(amount, max_by_pct, precision_digits=2) > 0:
                amount = max_by_pct
                cap_applied = True
                cap_reasons.append(
                    f'scheme max {max_pct}% cap (≤ {max_by_pct:,.2f})'
                )

        if max_amt > 0:
            if float_compare(amount, max_amt, precision_digits=2) > 0:
                amount = max_amt
                cap_applied = True
                cap_reasons.append(
                    f'scheme max amount cap (≤ {max_amt:,.2f})'
                )

        if float_compare(amount, 0.0, precision_digits=2) < 0:
            amount = 0.0

        cap_reason = '; '.join(cap_reasons) if cap_reasons else False
        return amount, cap_applied, cap_reason

    def _apply_total_cap(self, running_total, new_amount, eligible_total):
        """
        Apply the global total cap: running + new cannot exceed eligible_total.

        Returns: (allowed_amount: float, global_cap_triggered: bool)
        """
        combined = running_total + new_amount
        if float_compare(combined, eligible_total, precision_digits=2) > 0:
            allowed = max(0.0, float_round(
                eligible_total - running_total, precision_digits=2
            ))
            return allowed, True
        return float_round(new_amount, precision_digits=2), False

    def _compute_final_scholarship_discount(self):
        """
        Full calculation pipeline:
        1. Collect approved lines
        2. Validate stacking/exclusivity
        3. Sort by priority (ascending sequence, then type order)
        4. For each line:
            a. Compute raw discount from approved type/values
            b. Apply scheme-level caps (snapshot-based)
            c. Apply running total cap (never exceed eligible)
            d. Write calculated_discount_amount, cap_applied, cap_reason
        5. Return total applied discount

        This is the canonical entry point for the engine.
        """
        self.ensure_one()
        approved = self._get_approved_scholarship_lines()
        if not approved:
            return 0.0

        self._validate_scholarship_stacking(approved)
        sorted_lines = self._get_sorted_scholarship_lines(approved)
        eligible = self.scholarship_eligible_total or 0.0
        running_total = 0.0

        for line in sorted_lines:
            if not line.approved_type:
                _logger.warning(
                    'Scholarship review %s has no approved_type set, skipping.',
                    line.display_name,
                )
                continue
            raw = line._calculate_raw_discount(eligible)
            capped, scheme_cap, scheme_cap_reason = self._apply_scheme_caps(
                line, raw, eligible
            )
            final, total_cap = self._apply_total_cap(
                running_total, capped, eligible
            )

            cap_applied = scheme_cap or total_cap
            cap_reasons = []
            if scheme_cap_reason:
                cap_reasons.append(scheme_cap_reason)
            if total_cap:
                cap_reasons.append('global eligible-amount cap')

            line.write({
                'calculated_discount_amount': final,
                'cap_applied': cap_applied,
                'cap_reason': '; '.join(cap_reasons) if cap_reasons else False,
            })
            running_total += final

        return float_round(running_total, precision_digits=2)

    def _recompute_scholarship_summary(self):
        """
        Entry point called after any scholarship review state change.
        Delegates to _compute_final_scholarship_discount for the full pipeline.
        """
        self.ensure_one()
        if self.scholarship_frozen:
            return
        self._compute_final_scholarship_discount()

    def action_freeze_scholarship_outcome(self):
        """
        Explicitly freeze the scholarship outcome.

        Called automatically from action_accept_offer.
        After freezing:
        - approved review lines cannot be edited (protected by write() lock)
        - scholarship_frozen = True prevents further recalculation
        - scholarship_freeze_date is recorded for audit

        Can be called manually by admins on a non-frozen application if needed
        to lock scholarship outcome before offer acceptance (edge case).
        """
        self.ensure_one()
        if self.scholarship_frozen:
            return  # already frozen, idempotent
        # Run a final recalculation before locking
        self._compute_final_scholarship_discount()
        self.write({
            'scholarship_frozen': True,
            'scholarship_freeze_date': fields.Datetime.now(),
        })

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
    def _check_enrollment_readiness(self):
        """
        Raise UserError listing all reasons that prevent enrollment creation.
        Call before any enrollment creation logic.
        """
        self.ensure_one()
        blocks = self._get_enrollment_block_reasons()
        if blocks:
            raise UserError(
                f'Application "{self.application_no}" is not ready for '
                'enrollment:\n'
                + '\n'.join(f'  • {b}' for b in blocks)
            )

    def _prepare_enrollment_vals(self):
        """
        Build a values dict for creating an edu.enrollment record.

        Field names match edu.enrollment exactly (application_id,
        payment_plan_id, etc.).  All academic and financial fields are
        snapshotted so they remain historically stable.

        current_program_term_id is derived from batch.current_program_term_id
        at the moment of enrollment preparation — it is NOT stored on the
        application itself.

        Called internally by action_create_enrollment().
        Can be overridden in downstream modules.
        """
        self.ensure_one()
        self._check_enrollment_readiness()

        batch = self.batch_id
        program_term = batch.current_program_term_id if batch else False

        return {
            # ── Source linkage ──────────────────────────────────────────────
            'application_id': self.id,
            'applicant_profile_id': self.applicant_profile_id.id,
            # ── Academic placement (snapshots) ──────────────────────────────
            'program_id': self.program_id.id,
            'batch_id': batch.id if batch else False,
            'academic_year_id': (
                self.academic_year_id.id if self.academic_year_id else False
            ),
            'current_program_term_id': (
                program_term.id if program_term else False
            ),
            # ── Financial context (snapshots) ───────────────────────────────
            'fee_structure_id': (
                self.fee_structure_id.id if self.fee_structure_id else False
            ),
            'payment_plan_id': (
                self.selected_payment_plan_id.id
                if self.selected_payment_plan_id else False
            ),
            'base_total_fee': self.base_total_fee,
            'scholarship_eligible_total': self.scholarship_eligible_total,
            'total_scholarship_discount_amount': (
                self.total_scholarship_discount_amount
            ),
            'net_fee_after_scholarship': self.net_fee_after_scholarship,
            'scholarship_status': self.scholarship_status,
            'scholarship_cap_applied': self.scholarship_cap_applied,
            # ── Admission outcome (snapshots) ───────────────────────────────
            'fee_confirmed': self.fee_confirmed,
            'fee_confirmation_date': self.fee_confirmation_date,
            'offer_status': self.offer_status,
            'offer_acceptance_date': self.offer_acceptance_date,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    # NOTE: action_view_enrollment is defined in edu_enrollment's extension
    # (edu_enrollment/models/edu_admission_application.py) and requires
    # enrollment_ids / enrollment_count fields added by that module.

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
            if rec.scholarship_frozen:
                raise UserError(
                    f'Cannot recompute scholarships on "{rec.application_no}" — '
                    'the scholarship outcome is frozen after offer acceptance.'
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

    # ═════════════════════════════════════════════════════════════════════════
    # Scholarship Auto-Suggestion Engine
    # ═════════════════════════════════════════════════════════════════════════

    def action_suggest_scholarships(self):
        """
        Auto-suggest eligible scholarship schemes for this application.

        Searches all active schemes with auto_suggest_if_eligible=True,
        filters them against the application's context (program, department,
        academic year, applicant demographics, academic score), creates
        draft review lines for matching schemes not already linked, and
        runs the eligibility hint check on each new line.

        Returns a notification summarising what was suggested.
        """
        self.ensure_one()
        if self.scholarship_frozen:
            raise UserError(
                f'Cannot suggest scholarships on "{self.application_no}" — '
                'the scholarship outcome is frozen.'
            )

        # Collect candidate schemes
        candidates = self._get_auto_suggest_candidate_schemes()

        # Filter out schemes already linked to this application
        existing_scheme_ids = set(
            self.scholarship_review_ids.mapped('scholarship_scheme_id').ids
        )
        new_candidates = candidates.filtered(
            lambda s: s.id not in existing_scheme_ids
        )

        if not new_candidates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No New Scholarships',
                    'message': (
                        'No additional scholarship schemes match this '
                        'application\'s criteria, or all eligible schemes '
                        'are already linked.'
                    ),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        # Create draft review lines and run eligibility hints
        ReviewModel = self.env['edu.admission.scholarship.review']
        created_lines = self.env['edu.admission.scholarship.review']

        for scheme in new_candidates:
            line = ReviewModel.create({
                'application_id': self.id,
                'scholarship_scheme_id': scheme.id,
                'sequence': scheme.priority,
            })
            # Trigger onchange to pre-fill recommendation from scheme defaults
            line._onchange_scheme()
            # Run eligibility hint check
            line._auto_fill_eligibility_hint()
            created_lines |= line

        suggested_names = ', '.join(created_lines.mapped(
            'scholarship_scheme_id.name'
        ))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'{len(created_lines)} Scholarship(s) Suggested',
                'message': (
                    f'Draft review lines created for: {suggested_names}. '
                    'Review eligibility notes and proceed with assessment.'
                ),
                'type': 'success',
                'sticky': True,
            },
        }

    def _get_auto_suggest_candidate_schemes(self):
        """
        Return scholarship schemes eligible for auto-suggestion based on
        the application's context and the applicant's profile.

        Filtering pipeline:
        1. Active schemes with auto_suggest_if_eligible=True
        2. Validity date window (valid_from / valid_to)
        3. Program applicability
        4. Department applicability
        5. Academic year applicability
        6. Gender applicability
        7. Nationality applicability
        8. Age range applicability
        9. Minimum academic score applicability
        """
        SchemeModel = self.env['edu.scholarship.scheme']
        today = fields.Date.today()

        # Step 1: base domain — active and auto-suggest enabled
        domain = [
            ('active', '=', True),
            ('auto_suggest_if_eligible', '=', True),
        ]

        # Step 2: validity date window
        domain += [
            '|', ('valid_from', '=', False), ('valid_from', '<=', today),
        ]
        domain += [
            '|', ('valid_to', '=', False), ('valid_to', '>=', today),
        ]

        candidates = SchemeModel.search(domain)

        if not candidates:
            return candidates

        # Gather application and profile context
        profile = self.applicant_profile_id
        program = self.program_id
        department = self.department_id
        academic_year = self.academic_year_id
        gender = profile.gender if profile else False
        nationality = profile.nationality_id if profile else False
        age = profile.age if profile else 0

        # Get highest-completed academic history for score check
        highest_history = False
        if profile:
            highest_history = profile.academic_history_ids.filtered(
                lambda h: h.is_highest_completed
            )[:1]

        # Filter candidates through applicability rules
        result = self.env['edu.scholarship.scheme']
        for scheme in candidates:
            if not self._scheme_matches_application(
                scheme, program, department, academic_year,
                gender, nationality, age, highest_history,
            ):
                continue
            result |= scheme

        return result

    def _scheme_matches_application(
        self, scheme, program, department, academic_year,
        gender, nationality, age, highest_history,
    ):
        """
        Check if a single scheme's applicability filters match the
        application's context. Returns True if the scheme is applicable.

        Empty filter fields (M2M with no records, selection='any', int=0)
        mean 'no restriction' — the scheme applies to all in that dimension.
        """
        # Program filter
        if scheme.applicable_program_ids and program:
            if program not in scheme.applicable_program_ids:
                return False
        elif scheme.applicable_program_ids and not program:
            return False  # scheme requires specific programs but app has none

        # Department filter
        if scheme.applicable_department_ids and department:
            if department not in scheme.applicable_department_ids:
                return False
        elif scheme.applicable_department_ids and not department:
            return False

        # Academic year filter
        if scheme.applicable_academic_year_ids and academic_year:
            if academic_year not in scheme.applicable_academic_year_ids:
                return False
        elif scheme.applicable_academic_year_ids and not academic_year:
            return False

        # Gender filter
        if scheme.applicable_gender and scheme.applicable_gender != 'any':
            if not gender or gender != scheme.applicable_gender:
                return False

        # Nationality filter
        if scheme.applicable_nationality_ids:
            if not nationality or nationality not in scheme.applicable_nationality_ids:
                return False

        # Age range filter
        if scheme.min_applicant_age and age < scheme.min_applicant_age:
            return False
        if scheme.max_applicant_age and age > scheme.max_applicant_age:
            return False

        # Academic score filter
        if scheme.min_academic_score > 0:
            if not highest_history:
                return False  # no academic history → can't verify score
            # Check score type compatibility
            if (
                scheme.academic_score_type
                and scheme.academic_score_type != 'any'
                and highest_history.score_type != scheme.academic_score_type
            ):
                return False  # score type mismatch
            if highest_history.score < scheme.min_academic_score:
                return False  # score too low

        return True
