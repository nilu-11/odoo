from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduScholarshipScheme(models.Model):
    """
    Master scholarship definition / catalog.

    Defines the award type, eligibility category, stacking/exclusivity rules,
    capping limits, and category-specific eligibility hints.

    Scheme master data drives behaviour for all review lines that reference it.
    Policy changes to schemes do NOT retroactively alter already-approved review
    lines — those are protected by snapshot fields on the review record.
    """

    _name = 'edu.scholarship.scheme'
    _description = 'Scholarship Scheme'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority, name'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Scheme Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Code',
        tracking=True,
        help='Short identifier, e.g. MERIT-100, SIBLING-10.',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ── Category / Eligibility Basis ──────────────────────────────────────────
    eligibility_basis = fields.Selection(
        selection=[
            ('merit',        'Merit'),
            ('financial_aid', 'Financial Aid / Need-Based'),
            ('sibling',      'Sibling'),
            ('sports',       'Sports'),
            ('staff_child',  'Staff Child'),
            ('quota',        'Quota / Reservation'),
            ('promotional',  'Promotional / Marketing'),
            ('partner',      'Partner / Affiliate'),
            ('full',         'Full Scholarship'),
            ('discretionary', 'Manual Discretionary'),
            # Legacy aliases kept for backwards-compat with existing data
            ('need',         'Need-Based (legacy)'),
            ('manual',       'Manual (legacy)'),
            ('other',        'Other'),
        ],
        string='Scholarship Category',
        required=True,
        tracking=True,
        help=(
            'Broad classification that drives eligibility hint display '
            'and reporting groupings.'
        ),
    )

    # ── Award Configuration ───────────────────────────────────────────────────
    award_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage of Eligible Amount'),
            ('fixed',      'Fixed Amount'),
            ('full',       'Full Scholarship (100%)'),
            ('custom',     'Custom / Manual Amount'),
        ],
        string='Award Type',
        required=True,
        default='percentage',
        tracking=True,
    )
    default_percent = fields.Float(
        string='Default Percent',
        digits=(5, 2),
        help='Default % discount pre-filled on review lines (percentage award type).',
    )
    default_amount = fields.Float(
        string='Default Amount',
        digits=(12, 2),
        help='Default fixed amount pre-filled on review lines (fixed award type).',
    )

    # ── Applicability ─────────────────────────────────────────────────────────
    applies_on = fields.Selection(
        selection=[
            ('scholarship_eligible', 'Scholarship-Eligible Fee Components'),
            ('tuition_only',         'Tuition Only'),
            ('selected_fee_heads',   'Selected Fee Heads'),
        ],
        string='Applies On',
        default='scholarship_eligible',
        required=True,
        help=(
            'Which fee components this scholarship discounts.\n'
            '• Scholarship-Eligible: all fee lines where scholarship_allowed=True\n'
            '• Tuition Only: fee lines with fee_type=tuition\n'
            '• Selected Fee Heads: specific fee heads chosen below'
        ),
    )
    fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        relation='edu_scholarship_scheme_fee_head_rel',
        column1='scheme_id',
        column2='fee_head_id',
        string='Applicable Fee Heads',
        help='Specific fee heads this scheme applies to (applies_on=selected_fee_heads).',
    )

    # ── Review Behaviour Flags ────────────────────────────────────────────────
    requires_manual_review = fields.Boolean(
        string='Requires Manual Review',
        default=False,
        tracking=True,
        help='Review officer must manually assess eligibility before recommendation.',
    )
    requires_document_verification = fields.Boolean(
        string='Requires Document Verification',
        default=False,
        help='Supporting documents must be verified before approval.',
    )
    requires_committee_approval = fields.Boolean(
        string='Requires Committee Approval',
        default=False,
        help='A committee or senior officer must approve (not just the reviewer).',
    )
    auto_suggest_if_eligible = fields.Boolean(
        string='Auto-Suggest When Eligible',
        default=False,
        help=(
            'If eligibility hints are satisfied, the system will flag this '
            'scheme as a suggestion on the review. Does NOT auto-approve.'
        ),
    )
    # Kept for backwards-compat; prefer the three flags above for new schemes
    requires_approval = fields.Boolean(
        string='Requires Explicit Approval',
        default=True,
        help='Whether scholarship awards require explicit approval before finalisation.',
    )

    # ── Stacking / Exclusivity ────────────────────────────────────────────────
    allow_stacking = fields.Boolean(
        string='Allow Stacking',
        default=True,
        tracking=True,
        help='If True, can be combined with other stackable scholarships.',
    )
    exclusive = fields.Boolean(
        string='Exclusive',
        default=False,
        tracking=True,
        help='If True, cannot be combined with ANY other scholarship.',
    )
    stacking_group_id = fields.Many2one(
        comodel_name='edu.scholarship.stacking.group',
        string='Stacking Group',
        ondelete='set null',
        help=(
            'Optional group for cross-scheme stacking rules. '
            'Only one scheme per stacking group is allowed when '
            'the group disallows multi-scheme stacking.'
        ),
    )
    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Lower = higher priority. Determines calculation order when stacking.',
    )

    # ── Caps ──────────────────────────────────────────────────────────────────
    max_discount_percent = fields.Float(
        string='Max Discount %',
        digits=(5, 2),
        default=0.0,
        help='Maximum award as % of eligible total. 0 = no percent cap.',
    )
    max_discount_amount = fields.Float(
        string='Max Discount Amount',
        digits=(12, 2),
        default=0.0,
        help='Maximum award as fixed amount. 0 = no amount cap.',
    )
    institutional_cap_exempt = fields.Boolean(
        string='Exempt from Institutional Cap',
        default=False,
        help=(
            'If True, this scheme is excluded from institution-wide global '
            'discount cap calculations (e.g. government-funded full scholarships).'
        ),
    )

    # ── Validity ──────────────────────────────────────────────────────────────
    valid_from = fields.Date(
        string='Valid From',
        help='This scheme is only available for applications from this date.',
    )
    valid_to = fields.Date(
        string='Valid To',
        help='This scheme is only available for applications up to this date.',
    )
    intake_limited = fields.Boolean(
        string='Intake-Limited',
        default=False,
        help='Scheme applies only to a specific intake / batch (set via valid dates).',
    )
    renewable = fields.Boolean(
        string='Renewable',
        default=False,
        help='Whether this scholarship can be renewed for subsequent academic periods.',
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORY-SPECIFIC ELIGIBILITY HINTS
    # These are advisory — the engine never auto-approves based on hints alone.
    # Reviewers use them to evaluate eligibility; approval remains human-controlled.
    # ══════════════════════════════════════════════════════════════════════════

    # ── Merit Hints ───────────────────────────────────────────────────────────
    merit_score_type = fields.Selection(
        selection=[
            ('percentage',    'Percentage / Marks'),
            ('gpa',           'GPA'),
            ('rank',          'Rank / Position'),
            ('entrance_score', 'Entrance Exam Score'),
            ('manual',        'Manual Assessment'),
        ],
        string='Merit Score Basis',
        help='Which scoring basis is used to assess merit eligibility.',
    )
    merit_min_score = fields.Float(
        string='Minimum Merit Score',
        digits=(7, 2),
        help=(
            'Minimum score required for this merit scheme. '
            'Interpretation depends on merit_score_type.'
        ),
    )

    # ── Financial Aid Hints ───────────────────────────────────────────────────
    max_family_income = fields.Float(
        string='Max Annual Family Income',
        digits=(14, 2),
        help='Upper family income limit for financial aid eligibility.',
    )

    # ── Sibling Hints ─────────────────────────────────────────────────────────
    sibling_required_count = fields.Integer(
        string='Min. Sibling Count',
        default=1,
        help='Minimum number of enrolled siblings required for eligibility.',
    )

    # ── Sports Hints ──────────────────────────────────────────────────────────
    sports_level = fields.Selection(
        selection=[
            ('district',      'District Level'),
            ('state',         'State Level'),
            ('national',      'National Level'),
            ('international', 'International Level'),
            ('institutional', 'Institutional / Internal'),
        ],
        string='Minimum Sports Level',
        help='Minimum sporting achievement level required.',
    )

    # ── Staff-Child Hints ─────────────────────────────────────────────────────
    staff_relation_required = fields.Char(
        string='Staff Relation Required',
        help='e.g. "child", "spouse", "sibling" — descriptive, used by reviewer.',
    )

    # ── Quota Hints ───────────────────────────────────────────────────────────
    quota_category_code = fields.Char(
        string='Quota Category Code',
        help='e.g. SC, ST, OBC, EWS, PWD — used for policy tracking and reporting.',
    )

    # ── Partner / Affiliate Hints ─────────────────────────────────────────────
    partner_code = fields.Char(
        string='Partner / Feeder Institution Code',
        help='Code of the partner or feeder institution this scheme applies to.',
    )
    # ══════════════════════════════════════════════════════════════════════════
    # APPLICABILITY FILTERS (Auto-Suggestion Scope)
    # These fields define which applications a scheme can be suggested for.
    # Empty M2M fields mean "applies to all" (no restriction).
    # ══════════════════════════════════════════════════════════════════════════

    applicable_program_ids = fields.Many2many(
        comodel_name='edu.program',
        relation='edu_scholarship_scheme_program_rel',
        column1='scheme_id',
        column2='program_id',
        string='Applicable Programs',
        help='Restrict this scheme to specific programs. Leave empty to apply to all.',
    )
    applicable_department_ids = fields.Many2many(
        comodel_name='edu.department',
        relation='edu_scholarship_scheme_department_rel',
        column1='scheme_id',
        column2='department_id',
        string='Applicable Departments',
        help='Restrict to specific departments. Leave empty to apply to all.',
    )
    applicable_academic_year_ids = fields.Many2many(
        comodel_name='edu.academic.year',
        relation='edu_scholarship_scheme_acad_year_rel',
        column1='scheme_id',
        column2='academic_year_id',
        string='Applicable Academic Years',
        help='Restrict to specific academic years / intakes. Leave empty for all.',
    )
    applicable_nationality_ids = fields.Many2many(
        comodel_name='res.country',
        relation='edu_scholarship_scheme_country_rel',
        column1='scheme_id',
        column2='country_id',
        string='Applicable Nationalities',
        help='Restrict to applicants of specific nationalities. Leave empty for all.',
    )
    applicable_gender = fields.Selection(
        selection=[
            ('any', 'Any'),
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        string='Applicable Gender',
        default='any',
        help='Restrict to a specific gender. "Any" means no gender filter.',
    )
    min_applicant_age = fields.Integer(
        string='Minimum Applicant Age',
        default=0,
        help='Minimum age of the applicant for eligibility. 0 = no minimum.',
    )
    max_applicant_age = fields.Integer(
        string='Maximum Applicant Age',
        default=0,
        help='Maximum age of the applicant. 0 = no maximum.',
    )
    min_academic_score = fields.Float(
        string='Minimum Academic Score',
        digits=(8, 2),
        default=0.0,
        help=(
            'Minimum score from the applicant\'s highest completed '
            'academic history record. 0 = no minimum. '
            'Compared against edu.applicant.academic.history.score '
            'where is_highest_completed=True.'
        ),
    )
    academic_score_type = fields.Selection(
        selection=[
            ('any', 'Any Score Type'),
            ('percentage', 'Percentage'),
            ('gpa', 'GPA'),
            ('cgpa', 'CGPA'),
        ],
        string='Academic Score Type',
        default='any',
        help='Which score type to compare against. "Any" accepts all types.',
    )
    # ── Notes ─────────────────────────────────────────────────────────────────
    note = fields.Text(string='Internal Notes')

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Scholarship scheme code must be unique per company.',
        ),
    ]

    # ── Python Constraints ────────────────────────────────────────────────────
    @api.constrains('exclusive', 'allow_stacking')
    def _check_exclusive_stacking(self):
        for rec in self:
            if rec.exclusive and rec.allow_stacking:
                raise ValidationError(
                    f'Scheme "{rec.name}" is marked exclusive — '
                    'it cannot also allow stacking.'
                )

    @api.constrains('default_percent')
    def _check_percent_range(self):
        for rec in self:
            if rec.default_percent < 0 or rec.default_percent > 100:
                raise ValidationError(
                    f'Default percent for "{rec.name}" must be between 0 and 100.'
                )

    @api.constrains('default_amount')
    def _check_amount_positive(self):
        for rec in self:
            if rec.default_amount < 0:
                raise ValidationError(
                    f'Default amount for "{rec.name}" cannot be negative.'
                )

    @api.constrains('applies_on', 'fee_head_ids')
    def _check_fee_heads_selected(self):
        for rec in self:
            if rec.applies_on == 'selected_fee_heads' and not rec.fee_head_ids:
                raise ValidationError(
                    f'Scheme "{rec.name}" applies on selected fee heads — '
                    'at least one fee head must be chosen.'
                )

    @api.constrains('valid_from', 'valid_to')
    def _check_validity_dates(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_from > rec.valid_to:
                raise ValidationError(
                    f'Scheme "{rec.name}": Valid From must be before Valid To.'
                )

    @api.constrains('max_discount_percent')
    def _check_max_percent_range(self):
        for rec in self:
            if rec.max_discount_percent < 0 or rec.max_discount_percent > 100:
                raise ValidationError(
                    f'Max discount % for "{rec.name}" must be between 0 and 100.'
                )

    @api.constrains('max_discount_amount')
    def _check_max_amount_positive(self):
        for rec in self:
            if rec.max_discount_amount < 0:
                raise ValidationError(
                    f'Max discount amount for "{rec.name}" cannot be negative.'
                )

    @api.constrains('min_applicant_age', 'max_applicant_age')
    def _check_age_range(self):
        for rec in self:
            if rec.min_applicant_age < 0:
                raise ValidationError(
                    f'Minimum applicant age for "{rec.name}" cannot be negative.'
                )
            if rec.max_applicant_age < 0:
                raise ValidationError(
                    f'Maximum applicant age for "{rec.name}" cannot be negative.'
                )
            if (
                rec.min_applicant_age
                and rec.max_applicant_age
                and rec.min_applicant_age > rec.max_applicant_age
            ):
                raise ValidationError(
                    f'Scheme "{rec.name}": minimum age ({rec.min_applicant_age}) '
                    f'cannot exceed maximum age ({rec.max_applicant_age}).'
                )

    @api.constrains('min_academic_score')
    def _check_min_academic_score(self):
        for rec in self:
            if rec.min_academic_score < 0:
                raise ValidationError(
                    f'Minimum academic score for "{rec.name}" cannot be negative.'
                )

    # ── Onchange Helpers ──────────────────────────────────────────────────────
    @api.onchange('exclusive')
    def _onchange_exclusive(self):
        if self.exclusive:
            self.allow_stacking = False

    @api.onchange('award_type')
    def _onchange_award_type(self):
        """Reset irrelevant default fields when award type changes."""
        if self.award_type == 'full':
            self.default_percent = 100.0
            self.default_amount = 0.0
        elif self.award_type == 'percentage':
            self.default_amount = 0.0
        elif self.award_type == 'fixed':
            self.default_percent = 0.0
        elif self.award_type == 'custom':
            self.default_percent = 0.0
            self.default_amount = 0.0
