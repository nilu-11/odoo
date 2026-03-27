from odoo import api, fields, models
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
    institutional_cap_exempt_snapshot = fields.Boolean(
        string='Institutional Cap Exempt (Snapshot)', readonly=True,
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

    # ── Eligibility Hint Check ────────────────────────────────────────────────
    def _check_scheme_eligibility_hint(self):
        """
        Compare application / applicant data against scheme eligibility hints
        and return a dict with keys:
            - 'result':  'eligible' | 'not_eligible' | 'insufficient_data'
            - 'reasons': list[str]  — human-readable evaluation points

        This is advisory only. It never auto-approves.
        The reviewer uses this output to populate eligibility_result/note.
        """
        self.ensure_one()
        scheme = self.scholarship_scheme_id
        app = self.application_id
        reasons = []
        result = 'eligible'

        basis = scheme.eligibility_basis

        if basis == 'merit':
            if scheme.merit_min_score and scheme.merit_score_type != 'manual':
                reasons.append(
                    f'Merit basis: {scheme.merit_score_type} — '
                    f'min required {scheme.merit_min_score}. '
                    'Verify applicant score manually.'
                )
            else:
                reasons.append('Merit basis: manual assessment required.')
            result = 'pending'

        elif basis in ('financial_aid', 'need'):
            if scheme.max_family_income:
                reasons.append(
                    f'Financial aid: max annual family income '
                    f'{scheme.max_family_income:,.2f}. '
                    'Verify income documents.'
                )
            else:
                reasons.append('Financial aid: income threshold not configured.')
            result = 'pending'

        elif basis == 'sibling':
            reasons.append(
                f'Sibling scheme: minimum {scheme.sibling_required_count} '
                'enrolled sibling(s) required. Verify enrollment records.'
            )
            result = 'pending'

        elif basis == 'sports':
            if scheme.sports_level:
                reasons.append(
                    f'Sports scheme: minimum {scheme.sports_level} level '
                    'achievement required. Verify certificates.'
                )
            else:
                reasons.append('Sports scheme: level not configured — manual check.')
            result = 'pending'

        elif basis == 'staff_child':
            if scheme.staff_relation_required:
                reasons.append(
                    f'Staff-child scheme: relation "{scheme.staff_relation_required}" '
                    'must be verified against HR records.'
                )
            else:
                reasons.append('Staff-child scheme: manual HR verification required.')
            result = 'pending'

        elif basis == 'quota':
            if scheme.quota_category_code:
                reasons.append(
                    f'Quota scheme: category "{scheme.quota_category_code}". '
                    'Verify quota category certificate.'
                )
            else:
                reasons.append('Quota scheme: category code not configured.')
            result = 'pending'

        elif basis == 'promotional':
            if scheme.valid_from or scheme.valid_to:
                reasons.append(
                    f'Promotional scheme valid '
                    f'{scheme.valid_from or "—"} to {scheme.valid_to or "—"}.'
                )
            result = 'eligible'

        elif basis == 'partner':
            if scheme.partner_code:
                reasons.append(
                    f'Partner scheme: partner code "{scheme.partner_code}". '
                    'Verify applicant feeder institution.'
                )
            else:
                reasons.append('Partner scheme: partner code not configured.')
            result = 'pending'

        elif basis in ('full',):
            reasons.append('Full scholarship: manual review and committee approval required.')
            result = 'pending'

        elif basis in ('discretionary', 'manual'):
            reasons.append('Discretionary scheme: case-by-case authorised approval required.')
            result = 'pending'

        else:
            reasons.append('Eligibility basis not configured — manual assessment required.')
            result = 'insufficient_data'

        # Additional scheme-level review requirements
        if scheme.requires_document_verification:
            reasons.append('Document verification required before approval.')
        if scheme.requires_committee_approval:
            reasons.append('Committee approval required.')

        return {'result': result, 'reasons': reasons}

    def action_check_eligibility_hint(self):
        """
        Run eligibility hint check and populate eligibility fields on this line.
        Does NOT change state or approve anything.
        """
        self.ensure_one()
        hint = self._check_scheme_eligibility_hint()
        self.eligibility_checked = True
        self.eligibility_result = (
            hint['result'] if hint['result'] in ('eligible', 'not_eligible')
            else 'pending'
        )
        note = '\n'.join(hint['reasons'])
        self.eligibility_note = note
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Eligibility Hints',
                'message': note or 'No hints configured for this scheme.',
                'type': 'info',
                'sticky': True,
            },
        }

    def _auto_fill_eligibility_hint(self):
        """
        Silently run the eligibility hint check and populate eligibility
        fields. Used by the auto-suggestion engine — no UI notification.
        Also appends applicability match notes based on scheme filters.
        """
        self.ensure_one()
        hint = self._check_scheme_eligibility_hint()

        # Append applicability context from auto-suggestion filters
        scheme = self.scholarship_scheme_id
        app = self.application_id
        profile = app.applicant_profile_id
        extra = []

        if scheme.applicable_program_ids:
            extra.append(
                f'Program filter matched: {app.program_id.name}'
            )
        if scheme.applicable_department_ids:
            extra.append(
                f'Department filter matched: {app.department_id.name}'
            )
        if scheme.applicable_academic_year_ids:
            extra.append(
                f'Academic year filter matched: {app.academic_year_id.name}'
            )
        if scheme.applicable_gender and scheme.applicable_gender != 'any':
            extra.append(
                f'Gender filter matched: {profile.gender}'
            )
        if scheme.applicable_nationality_ids and profile.nationality_id:
            extra.append(
                f'Nationality filter matched: {profile.nationality_id.name}'
            )
        if scheme.min_applicant_age and profile:
            extra.append(f'Applicant age ({profile.age}) >= minimum ({scheme.min_applicant_age})')
        if scheme.max_applicant_age and profile:
            extra.append(f'Applicant age ({profile.age}) <= maximum ({scheme.max_applicant_age})')
        if scheme.min_academic_score > 0 and profile:
            highest = profile.academic_history_ids.filtered(
                lambda h: h.is_highest_completed
            )[:1]
            if highest:
                extra.append(
                    f'Academic score ({highest.score} {highest.score_type}) '
                    f'>= minimum ({scheme.min_academic_score})'
                )

        all_reasons = hint['reasons'] + extra
        self.eligibility_checked = True
        self.eligibility_result = (
            hint['result'] if hint['result'] in ('eligible', 'not_eligible')
            else 'pending'
        )
        self.eligibility_note = '\n'.join(all_reasons)

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
        to recommend.  Combines scheme defaults with any eligibility hint
        results already recorded on this line.

        Returns: dict
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
            'requires_manual_review': scheme.requires_manual_review,
            'requires_document_verification': scheme.requires_document_verification,
            'requires_committee_approval': scheme.requires_committee_approval,
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
        for rec in self:
            if rec.state not in ('draft', 'under_review', 'recommended'):
                raise UserError(
                    f'Cannot approve review in "{rec.state}" state.'
                )
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
                'institutional_cap_exempt_snapshot': scheme.institutional_cap_exempt,
            })

        # Trigger recalc on parent applications (outside per-rec loop for batching)
        apps = self.mapped('application_id')
        for app in apps:
            if not app.scholarship_frozen:
                app._recompute_scholarship_summary()

    def action_reject(self):
        """Reject this scholarship review line."""
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
            'institutional_cap_exempt_snapshot': False,
        })
