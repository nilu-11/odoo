from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduScholarshipScheme(models.Model):
    """
    Master scholarship definition / catalog.

    Defines the award type, eligibility category, stacking/exclusivity rules,
    and capping limits.

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

    # ── Category ─────────────────────────────────────────────────────────────
    eligibility_basis = fields.Selection(
        selection=[
            ('merit', 'Merit'),
            ('financial_aid', 'Financial Aid / Need-Based'),
            ('sibling', 'Sibling'),
            ('sports', 'Sports'),
            ('staff_child', 'Staff Child'),
            ('quota', 'Quota / Reservation'),
            ('promotional', 'Promotional / Marketing'),
            ('partner', 'Partner / Affiliate'),
            ('full', 'Full Scholarship'),
            ('discretionary', 'Manual Discretionary'),
            ('other', 'Other'),
        ],
        string='Category',
        required=True,
        tracking=True,
    )

    # ── Merit Criteria (only for merit schemes) ────────────────────────────────
    merit_score_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('gpa', 'GPA'),
            ('cgpa', 'CGPA'),
        ],
        string='Required Score Type',
        help='Score type the applicant must have to qualify for this merit scheme.',
    )
    merit_min_score = fields.Float(
        string='Minimum Score',
        digits=(5, 2),
        help='Minimum score required for auto-suggestion. E.g. 80 for 80%, 3.5 for GPA.',
    )

    # ── Award Configuration ───────────────────────────────────────────────────
    award_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage of Eligible Amount'),
            ('fixed', 'Fixed Amount'),
            ('full', 'Full Scholarship (100%)'),
            ('custom', 'Custom / Manual Amount'),
        ],
        string='Award Type',
        required=True,
        default='percentage',
        tracking=True,
    )
    default_percent = fields.Float(
        string='Default Percent',
        digits=(5, 2),
        help='Default % discount pre-filled on review lines.',
    )
    default_amount = fields.Float(
        string='Default Amount',
        digits=(12, 2),
        help='Default fixed amount pre-filled on review lines.',
    )

    # ── Applicability ─────────────────────────────────────────────────────────
    applies_on = fields.Selection(
        selection=[
            ('scholarship_eligible', 'Scholarship-Eligible Fee Components'),
            ('tuition_only', 'Tuition Only'),
            ('selected_fee_heads', 'Selected Fee Heads'),
        ],
        string='Applies On',
        default='scholarship_eligible',
        required=True,
    )
    fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        relation='edu_scholarship_scheme_fee_head_rel',
        column1='scheme_id',
        column2='fee_head_id',
        string='Applicable Fee Heads',
    )

    # ── Scope ────────────────────────────────────────────────────────────────
    applicable_program_ids = fields.Many2many(
        comodel_name='edu.program',
        relation='edu_scholarship_scheme_program_rel',
        column1='scheme_id',
        column2='program_id',
        string='Programs',
        help='Restrict to specific programs. Leave empty for all.',
    )
    applicable_academic_year_ids = fields.Many2many(
        comodel_name='edu.academic.year',
        relation='edu_scholarship_scheme_acad_year_rel',
        column1='scheme_id',
        column2='academic_year_id',
        string='Academic Years',
        help='Restrict to specific academic years. Leave empty for all.',
    )

    # ── Suggestion ───────────────────────────────────────────────────────────
    auto_suggest = fields.Boolean(
        string='Auto-Suggest',
        default=False,
        help=(
            'When ticked, this scheme is automatically suggested on '
            'matching applications. Leave off for schemes that require '
            'student application or manual addition (e.g. sports, merit, quota).'
        ),
    )

    # ── Stacking / Exclusivity ────────────────────────────────────────────────
    allow_stacking = fields.Boolean(
        string='Allow Stacking',
        default=True,
        tracking=True,
        help='Can be combined with other stackable scholarships.',
    )
    exclusive = fields.Boolean(
        string='Exclusive',
        default=False,
        tracking=True,
        help='Cannot be combined with ANY other scholarship.',
    )
    stacking_group_id = fields.Many2one(
        comodel_name='edu.scholarship.stacking.group',
        string='Stacking Group',
        ondelete='set null',
    )
    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Lower = higher priority. Determines calculation order.',
    )

    # ── Caps ──────────────────────────────────────────────────────────────────
    max_discount_percent = fields.Float(
        string='Max Discount %',
        digits=(5, 2),
        default=0.0,
        help='Maximum award as % of eligible total. 0 = no cap.',
    )
    max_discount_amount = fields.Float(
        string='Max Discount Amount',
        digits=(12, 2),
        default=0.0,
        help='Maximum award as fixed amount. 0 = no cap.',
    )
    # ── Validity ──────────────────────────────────────────────────────────────
    valid_from = fields.Date(string='Valid From')
    valid_to = fields.Date(string='Valid To')

    # ── Notes ────────────────────────────────────────────────────────────────
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

    # ── Onchange Helpers ──────────────────────────────────────────────────────
    @api.onchange('exclusive')
    def _onchange_exclusive(self):
        if self.exclusive:
            self.allow_stacking = False

    @api.onchange('award_type')
    def _onchange_award_type(self):
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
