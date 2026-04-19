from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduAdmissionScholarshipReview(models.Model):
    """
    Per-application scholarship assessment / decision record.

    Lifecycle:
        draft → under_review → recommended → approved
                                           ↘ rejected
                             ↘ cancelled

    Each line references a scholarship scheme and captures:
    - Eligibility assessment (checked / result / notes)
    - Recommended values (reviewer proposal)
    - Approved values (final authorised decision)
    - Snapshot of ALL scheme rules at approval time (audit stability)
    - Cap reason when the award is reduced by a cap

    An application may have multiple review lines for different schemes.
    Stacking and capping are evaluated by the parent application engine.
    """

    _name = 'edu.admission.scholarship.review'
    _description = 'Admission Scholarship Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    _rec_name = 'display_name'

    # ── Identity ──────────────────────────────────────────────────────────────
    application_id = fields.Many2one(
        comodel_name='edu.admission.application',
        string='Application',
        required=True,
        ondelete='cascade',
        index=True,
    )
    scholarship_scheme_id = fields.Many2one(
        comodel_name='edu.scholarship.scheme',
        string='Scholarship Scheme',
        required=True,
        ondelete='restrict',
        index=True,
    )
    sequence = fields.Integer(
        string='Priority',
        default=10,
        help='Lower number = higher priority. Controls calculation order.',
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft',        'Draft'),
            ('under_review', 'Under Review'),
            ('recommended',  'Recommended'),
            ('approved',     'Approved'),
            ('rejected',     'Rejected'),
            ('cancelled',    'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Eligibility Assessment ────────────────────────────────────────────────
    eligibility_checked = fields.Boolean(
        string='Eligibility Checked',
        default=False,
        help='Reviewer has assessed eligibility against scheme criteria.',
    )
    eligibility_result = fields.Selection(
        selection=[
            ('eligible',      'Eligible'),
            ('not_eligible',  'Not Eligible'),
            ('pending',       'Pending Assessment'),
            ('overridden',    'Override / Discretionary'),
        ],
        string='Eligibility Result',
        tracking=True,
        help=(
            'Result of the eligibility assessment.\n'
            '"Override / Discretionary" means approved despite not strictly '
            'meeting the scheme criteria.'
        ),
    )
    eligibility_note = fields.Text(
        string='Eligibility Notes',
        help='Details of how eligibility was assessed against scheme hints.',
    )
    supporting_document_note = fields.Text(
        string='Supporting Documents',
        help=(
            'Notes on documents reviewed (income certificates, sports certificates, '
            'employment proof, etc.).'
        ),
    )
    financial_review_note = fields.Text(
        string='Financial Review Notes',
        help='Notes from the financial assessment (income, hardship, family background).',
    )
    committee_note = fields.Text(
        string='Committee / Approval Notes',
        help='Notes from the committee or senior approver.',
    )

    # ── Recommendation (reviewer proposal) ───────────────────────────────────
    recommendation_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('fixed',      'Fixed Amount'),
            ('full',       'Full Scholarship'),
            ('custom',     'Custom Amount'),
        ],
        string='Recommendation Type',
    )
    recommended_percent = fields.Float(
        string='Recommended %',
        digits=(5, 2),
    )
    recommended_amount = fields.Float(
        string='Recommended Amount',
        digits=(12, 2),
    )

    # ── Approved (final authorised decision) ──────────────────────────────────
    approved_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('fixed',      'Fixed Amount'),
            ('full',       'Full Scholarship'),
            ('custom',     'Custom Amount'),
        ],
        string='Approved Type',
        tracking=True,
    )
    approved_percent = fields.Float(
        string='Approved %',
        digits=(5, 2),
        tracking=True,
    )
    approved_amount = fields.Float(
        string='Approved Amount',
        digits=(12, 2),
        tracking=True,
    )

    # ── Calculated Outcome ────────────────────────────────────────────────────
    calculated_discount_amount = fields.Float(
        string='Calculated Discount',
        digits=(12, 2),
        readonly=True,
        help='Final calculated discount after all caps and stacking logic.',
    )
    eligible_base_amount_snapshot = fields.Float(
        string='Eligible Base (Snapshot)',
        digits=(12, 2),
        readonly=True,
        help=(
            'Snapshot of the application\'s scholarship_eligible_total '
            'at the moment of approval. Preserved for audit even if fee '
            'structure changes later.'
        ),
    )
    cap_applied = fields.Boolean(
        string='Cap Applied',
        default=False,
        readonly=True,
    )
    cap_reason = fields.Char(
        string='Cap Reason',
        readonly=True,
        help='Human-readable reason why a cap reduced this award.',
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    reviewed_by = fields.Many2one(
        comodel_name='res.users',
        string='Reviewed By',
        readonly=True,
        help='User who moved this line to Recommended state.',
    )
    reviewed_on = fields.Datetime(
        string='Reviewed On',
        readonly=True,
    )
    approved_by = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        help='Reason for rejecting this scholarship review.',
    )
    remarks = fields.Text(
        string='General Remarks',
        help='Justification, notes, observations — visible to all reviewers.',
    )

    # ── Scheme Snapshots (frozen at approval time) ────────────────────────────
    # These preserve historical correctness if the scheme master changes later.
    scheme_name_snapshot = fields.Char(
        string='Scheme Name (Snapshot)', readonly=True,
    )
    scheme_category_snapshot = fields.Char(
        string='Category (Snapshot)', readonly=True,
    )
    award_type_snapshot = fields.Char(
        string='Award Type (Snapshot)', readonly=True,
    )
    priority_snapshot = fields.Integer(
        string='Priority (Snapshot)', readonly=True,
    )
    exclusive_snapshot = fields.Boolean(
        string='Exclusive (Snapshot)', readonly=True,
    )
    stacking_allowed_snapshot = fields.Boolean(
        string='Stacking Allowed (Snapshot)', readonly=True,
    )
    stacking_group_snapshot = fields.Char(
        string='Stacking Group (Snapshot)', readonly=True,
    )
    eligibility_basis_snapshot = fields.Char(
        string='Eligibility Basis (Snapshot)', readonly=True,
    )
    applies_on_snapshot = fields.Char(
        string='Applies On (Snapshot)', readonly=True,
    )
    max_discount_percent_snapshot = fields.Float(
        string='Max Discount % (Snapshot)', digits=(5, 2), readonly=True,
    )
    max_discount_amount_snapshot = fields.Float(
        string='Max Discount Amount (Snapshot)', digits=(12, 2), readonly=True,
    )

    # ── Category Evidence (structured per eligibility_basis) ─────────────────
    # Related field for view conditions — no extra query needed
    eligibility_basis = fields.Selection(
        related='scholarship_scheme_id.eligibility_basis',
        string='Category',
        store=False,
    )

    # Merit
    merit_score_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('cgpa', 'CGPA'),
            ('grade', 'Grade'),
            ('rank', 'Rank / Position'),
        ],
        string='Score Type',
    )
    merit_min_score = fields.Float(
        string='Minimum Score Required',
        digits=(5, 2),
    )
    merit_actual_score = fields.Float(
        string='Actual Score Achieved',
        digits=(5, 2),
    )
    merit_certificate_ref = fields.Char(
        string='Marksheet / Certificate Ref',
    )
    merit_score_verified = fields.Boolean(
        string='Score Verified',
    )

    # Financial Aid
    financial_max_income = fields.Float(
        string='Income Limit (Annual)',
        digits=(12, 2),
    )
    financial_actual_income = fields.Float(
        string='Verified Annual Income',
        digits=(12, 2),
    )
    financial_certificate_ref = fields.Char(
        string='Income Certificate Ref',
    )
    financial_income_verified = fields.Boolean(
        string='Income Verified',
    )

    # Sibling
    sibling_min_count = fields.Integer(
        string='Min Enrolled Siblings Required',
        default=1,
    )
    sibling_details = fields.Text(
        string='Sibling Details',
        help='Names and enrollment / roll numbers of currently enrolled siblings.',
    )
    sibling_verified = fields.Boolean(
        string='Sibling Enrollment Verified',
    )

    # Sports
    sports_sport_name = fields.Char(
        string='Sport / Event',
    )
    sports_required_level = fields.Selection(
        selection=[
            ('school', 'School Level'),
            ('district', 'District Level'),
            ('state', 'State / Province Level'),
            ('national', 'National Level'),
            ('international', 'International Level'),
        ],
        string='Required Achievement Level',
    )
    sports_actual_level = fields.Selection(
        selection=[
            ('school', 'School Level'),
            ('district', 'District Level'),
            ('state', 'State / Province Level'),
            ('national', 'National Level'),
            ('international', 'International Level'),
        ],
        string='Actual Achievement Level',
    )
    sports_certificate_ref = fields.Char(
        string='Achievement Certificate Ref',
    )
    sports_verified = fields.Boolean(
        string='Achievement Verified',
    )

    # Staff Child
    staff_member_name = fields.Char(
        string='Staff Member Name',
    )
    staff_employee_id = fields.Char(
        string='Employee ID',
    )
    staff_relation = fields.Selection(
        selection=[
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('guardian', 'Legal Guardian'),
            ('sibling', 'Sibling'),
            ('spouse', 'Spouse'),
            ('other', 'Other'),
        ],
        string='Relation to Applicant',
    )
    staff_employment_verified = fields.Boolean(
        string='Employment Verified',
    )

    # Quota / Reservation
    quota_category = fields.Char(
        string='Reservation Category',
        help='e.g. OBC, SC, ST, EWS, PH, NRI — as per certificate.',
    )
    quota_certificate_number = fields.Char(
        string='Certificate Number',
    )
    quota_issuing_authority = fields.Char(
        string='Issuing Authority',
    )
    quota_certificate_verified = fields.Boolean(
        string='Certificate Verified',
    )

    # ── System ────────────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='application_id.company_id',
        string='Company',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='application_id.currency_id',
        string='Currency',
    )

    # ── Display Name ──────────────────────────────────────────────────────────
    @api.depends('application_id.application_no', 'scholarship_scheme_id.name')
    def _compute_display_name(self):
        for rec in self:
            app_no = rec.application_id.application_no or 'New'
            scheme = rec.scholarship_scheme_id.name or 'No Scheme'
            rec.display_name = f'{app_no} / {scheme}'

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_application_scheme',
            'UNIQUE(application_id, scholarship_scheme_id)',
            'Only one review line per scholarship scheme per application.',
        ),
    ]

    # ── Python Constraints ────────────────────────────────────────────────────
    @api.constrains('approved_percent')
    def _check_approved_percent(self):
        for rec in self:
            if rec.approved_percent < 0 or rec.approved_percent > 100:
                raise ValidationError(
                    'Approved percentage must be between 0 and 100.'
                )

    @api.constrains('approved_amount')
    def _check_approved_amount(self):
        for rec in self:
            if rec.approved_amount < 0:
                raise ValidationError('Approved amount cannot be negative.')

    @api.constrains('recommended_percent')
    def _check_recommended_percent(self):
        for rec in self:
            if rec.recommended_percent < 0 or rec.recommended_percent > 100:
                raise ValidationError(
                    'Recommended percentage must be between 0 and 100.'
                )

    @api.constrains('approved_type', 'approved_percent', 'approved_amount')
    def _check_approved_values_consistency(self):
        for rec in self:
            if rec.approved_type == 'full':
                if rec.approved_amount and float_compare(
                    rec.approved_amount, 0.0, precision_digits=2
                ) > 0:
                    raise ValidationError(
                        '"Full Scholarship" award type should not have a '
                        'fixed approved amount set. Clear it or use "Fixed Amount" type.'
                    )
            elif rec.approved_type == 'percentage' and rec.approved_percent == 0.0:
                pass  # Zero percent is technically valid (neutral discount)
            elif rec.approved_type == 'fixed' and rec.approved_amount < 0:
                raise ValidationError('Fixed approved amount cannot be negative.')

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('merit_actual_score', 'merit_min_score')
    def _onchange_merit_score(self):
        """Auto-suggest eligibility result when both scores are entered."""
        for rec in self:
            if rec.eligibility_basis != 'merit':
                continue
            if rec.merit_actual_score and rec.merit_min_score:
                rec.eligibility_result = (
                    'eligible' if rec.merit_actual_score >= rec.merit_min_score
                    else 'not_eligible'
                )

    @api.onchange('financial_actual_income', 'financial_max_income')
    def _onchange_financial_income(self):
        """Auto-suggest eligibility result based on income threshold."""
        for rec in self:
            if rec.eligibility_basis != 'financial_aid':
                continue
            if rec.financial_actual_income and rec.financial_max_income:
                rec.eligibility_result = (
                    'eligible' if rec.financial_actual_income <= rec.financial_max_income
                    else 'not_eligible'
                )

    @api.onchange('scholarship_scheme_id')
    def _onchange_scheme(self):
        """Pre-fill recommendation fields from scheme defaults."""
        scheme = self.scholarship_scheme_id
        if not scheme:
            return
        self.sequence = scheme.priority
        self.recommendation_type = (
            'full'       if scheme.award_type == 'full'
            else 'custom' if scheme.award_type == 'custom'
            else scheme.award_type if scheme.award_type in ('percentage', 'fixed')
            else 'percentage'
        )
        if scheme.award_type == 'percentage':
            self.recommended_percent = scheme.default_percent
        elif scheme.award_type == 'fixed':
            self.recommended_amount = scheme.default_amount
        elif scheme.award_type == 'full':
            self.recommended_percent = 100.0
        # pre-fill approved from recommendation as a convenience
        self.approved_type = self.recommendation_type
        self.approved_percent = self.recommended_percent
        self.approved_amount = self.recommended_amount

    # ── Write Locking ─────────────────────────────────────────────────────────
    def write(self, vals):
        """
        Prevent casual modification of approved review lines once the
        application is in a frozen state.
        """
        _PROTECTED = {
            'approved_type', 'approved_percent', 'approved_amount',
            'calculated_discount_amount', 'eligible_base_amount_snapshot',
            'scheme_name_snapshot', 'scheme_category_snapshot',
            'award_type_snapshot', 'exclusive_snapshot',
            'stacking_allowed_snapshot', 'max_discount_percent_snapshot',
            'max_discount_amount_snapshot',
        }
        changing_protected = _PROTECTED & set(vals.keys())
        if changing_protected:
            for rec in self:
                if (
                    rec.application_id.scholarship_frozen
                    and rec.state == 'approved'
                ):
                    raise UserError(
                        f'Cannot modify frozen scholarship review for '
                        f'"{rec.application_id.application_no}" — '
                        'the scholarship outcome is frozen after offer acceptance.'
                    )
        return super().write(vals)

    # ── Eligibility Hint Check (Removed — eligibility is assessed manually) ──

    # ── Discount Calculation ──────────────────────────────────────────────────
    def _calculate_raw_discount(self, eligible_total):
        """
        Calculate raw discount from approved values against the given
        eligible_total.  Does NOT apply caps — that is done by the engine.

        Returns: float
        """
        self.ensure_one()
        if self.approved_type == 'full':
            return float(eligible_total)
        elif self.approved_type == 'percentage':
            return float_round(
                eligible_total * (self.approved_percent or 0.0) / 100.0,
                precision_digits=2,
            )
        elif self.approved_type == 'fixed':
            return float(self.approved_amount or 0.0)
        elif self.approved_type == 'custom':
            return float(self.approved_amount or 0.0)
        return 0.0

    # ── Recommendation Context ────────────────────────────────────────────────
    def _prepare_recommendation_context(self):
        """
        Build a context dict used by reviewers / UI to understand what
        to recommend. Combines scheme defaults with eligibility results.
        """
        self.ensure_one()
        scheme = self.scholarship_scheme_id
        return {
            'scheme_name': scheme.name,
            'category': scheme.eligibility_basis,
            'award_type': scheme.award_type,
            'default_percent': scheme.default_percent,
            'default_amount': scheme.default_amount,
            'max_discount_percent': scheme.max_discount_percent,
            'max_discount_amount': scheme.max_discount_amount,
            'eligibility_result': self.eligibility_result,
            'eligibility_note': self.eligibility_note,
        }

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_start_review(self):
        """Move draft lines to under_review."""
        self.filtered(lambda r: r.state == 'draft').write(
            {'state': 'under_review'}
        )

    def action_recommend(self):
        """
        Reviewer recommends this scholarship.

        Sets state to 'recommended', records reviewed_by / reviewed_on.
        Approvers can then proceed to action_approve / action_reject.
        """
        for rec in self:
            if rec.state not in ('draft', 'under_review'):
                raise UserError(
                    f'Cannot recommend review in "{rec.state}" state.'
                )
            if not rec.recommendation_type:
                raise UserError(
                    'Set a recommendation type (percentage/fixed/full/custom) '
                    'before recommending.'
                )
            rec.write({
                'state': 'recommended',
                'reviewed_by': self.env.uid,
                'reviewed_on': fields.Datetime.now(),
            })

    def action_approve(self):
        """
        Approve this scholarship review line.

        Snapshots ALL current scheme rules so that historical approval
        decisions remain stable even if the scheme master is edited later.
        Triggers parent application recalculation.
        """
        if not self.env.user.has_group('edu_admission.group_scholarship_approver') and \
                not self.env.user.has_group('edu_academic_structure.group_education_admin'):
            raise UserError(
                _('Only Scholarship Approvers or Education Administrators '
                  'can approve scholarships.')
            )
        for rec in self:
            if rec.state not in ('draft', 'under_review', 'recommended'):
                raise UserError(
                    f'Cannot approve review in "{rec.state}" state.'
                )
            # Auto-fill from recommendation if approved values not set
            if not rec.approved_type and rec.recommendation_type:
                rec.write({
                    'approved_type': rec.recommendation_type,
                    'approved_percent': rec.recommended_percent,
                    'approved_amount': rec.recommended_amount,
                })
            if not rec.approved_type:
                raise UserError(
                    'Set an approved type (percentage/fixed/full/custom) '
                    'before approving.'
                )
            scheme = rec.scholarship_scheme_id
            eligible_total = rec.application_id.scholarship_eligible_total or 0.0
            rec.write({
                'state': 'approved',
                'approved_by': self.env.uid,
                'approval_date': fields.Datetime.now(),
                'eligible_base_amount_snapshot': eligible_total,
                # ── Full scheme snapshot ──────────────────────────────────
                'scheme_name_snapshot': scheme.name,
                'scheme_category_snapshot': scheme.eligibility_basis,
                'award_type_snapshot': scheme.award_type,
                'priority_snapshot': scheme.priority,
                'exclusive_snapshot': scheme.exclusive,
                'stacking_allowed_snapshot': scheme.allow_stacking,
                'stacking_group_snapshot': (
                    scheme.stacking_group_id.code
                    if scheme.stacking_group_id else False
                ),
                'eligibility_basis_snapshot': scheme.eligibility_basis,
                'applies_on_snapshot': scheme.applies_on,
                'max_discount_percent_snapshot': scheme.max_discount_percent,
                'max_discount_amount_snapshot': scheme.max_discount_amount,
            })

        # Auto-reject conflicting reviews on the same application
        self._auto_reject_conflicts()

        # Trigger recalc on parent applications (outside per-rec loop for batching)
        apps = self.mapped('application_id')
        for app in apps:
            if not app.scholarship_frozen:
                app._recompute_scholarship_summary()

    def _auto_reject_conflicts(self):
        """
        After approval, auto-reject other review lines that conflict:
        1. If approved scheme is exclusive → reject all other non-approved lines
        2. If approved scheme is non-stackable → reject all other non-approved lines
        3. Same stacking group → reject other lines in the same group
        """
        for rec in self.filtered(lambda r: r.state == 'approved'):
            app_lines = rec.application_id.scholarship_review_ids.filtered(
                lambda r: r.id != rec.id and r.state not in ('approved', 'rejected', 'cancelled')
            )
            if not app_lines:
                continue

            scheme = rec.scholarship_scheme_id
            to_reject = self.env['edu.admission.scholarship.review']

            # Exclusive: reject everything else
            if scheme.exclusive:
                to_reject = app_lines

            # Non-stackable: reject everything else
            elif not scheme.allow_stacking:
                to_reject = app_lines

            # Same stacking group: reject other lines in same group
            elif scheme.stacking_group_id:
                group_code = scheme.stacking_group_id.code
                to_reject = app_lines.filtered(
                    lambda r: r.scholarship_scheme_id.stacking_group_id.code == group_code
                )

            if to_reject:
                rejected_names = ', '.join(
                    to_reject.mapped('scholarship_scheme_id.name')
                )
                to_reject.write({
                    'state': 'rejected',
                    'rejection_reason': (
                        f'Auto-rejected: conflicts with approved scheme '
                        f'"{scheme.name}" '
                        f'({"exclusive" if scheme.exclusive else "same stacking group" if scheme.stacking_group_id else "non-stackable"}).'
                    ),
                })
                rec.application_id.message_post(
                    body=(
                        f'<p>Auto-rejected conflicting scholarships: '
                        f'<b>{rejected_names}</b> — conflicts with '
                        f'approved scheme "{scheme.name}".</p>'
                    ),
                    subtype_xmlid='mail.mt_note',
                )

    def action_reject(self):
        """Reject this scholarship review line."""
        if not self.env.user.has_group('edu_admission.group_scholarship_approver') and \
                not self.env.user.has_group('edu_academic_structure.group_education_admin'):
            raise UserError(
                _('Only Scholarship Approvers or Education Administrators '
                  'can reject scholarships.')
            )
        for rec in self:
            if rec.state == 'cancelled':
                raise UserError('Cannot reject a cancelled review.')
            if rec.application_id.scholarship_frozen and rec.state == 'approved':
                raise UserError(
                    'Cannot reject a frozen approved scholarship. '
                    'The application\'s scholarship outcome is already frozen.'
                )
        self.write({'state': 'rejected'})
        apps = self.mapped('application_id')
        for app in apps:
            if not app.scholarship_frozen:
                app._recompute_scholarship_summary()

    def action_cancel(self):
        """Cancel this scholarship review line."""
        for rec in self:
            if rec.application_id.scholarship_frozen and rec.state == 'approved':
                raise UserError(
                    'Cannot cancel a frozen approved scholarship review.'
                )
        self.write({
            'state': 'cancelled',
            'calculated_discount_amount': 0.0,
            'cap_applied': False,
            'cap_reason': False,
        })
        apps = self.mapped('application_id')
        for app in apps:
            if not app.scholarship_frozen:
                app._recompute_scholarship_summary()

    def action_reset_draft(self):
        """Reset a rejected or cancelled line back to draft."""
        for rec in self:
            if rec.application_id.scholarship_frozen:
                raise UserError(
                    'Cannot reset scholarship review — '
                    'the scholarship outcome is frozen after offer acceptance.'
                )
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(
                    f'Can only reset to draft from rejected or cancelled state '
                    f'(current: "{rec.state}").'
                )
        self.write({
            'state': 'draft',
            'approved_by': False,
            'approval_date': False,
            'reviewed_by': False,
            'reviewed_on': False,
            'calculated_discount_amount': 0.0,
            'cap_applied': False,
            'cap_reason': False,
            'eligible_base_amount_snapshot': 0.0,
            'priority_snapshot': 0,
            'exclusive_snapshot': False,
            'stacking_allowed_snapshot': False,
            'stacking_group_snapshot': False,
            'eligibility_basis_snapshot': False,
            'applies_on_snapshot': False,
            'scheme_name_snapshot': False,
            'scheme_category_snapshot': False,
            'award_type_snapshot': False,
            'max_discount_percent_snapshot': 0.0,
            'max_discount_amount_snapshot': 0.0,
        })
