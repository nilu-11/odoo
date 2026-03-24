from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduScholarshipScheme(models.Model):
    """
    Master scholarship definition / catalog.

    Defines the award type, eligibility basis, stacking/exclusivity rules,
    and cap limits. Schemes are referenced by scholarship review lines
    on individual admission applications.
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

    # ── Eligibility ───────────────────────────────────────────────────────────
    eligibility_basis = fields.Selection(
        selection=[
            ('merit', 'Merit'),
            ('need', 'Need-Based'),
            ('quota', 'Quota'),
            ('sports', 'Sports'),
            ('staff_child', 'Staff Child'),
            ('sibling', 'Sibling'),
            ('promotional', 'Promotional'),
            ('manual', 'Manual'),
            ('other', 'Other'),
        ],
        string='Eligibility Basis',
        required=True,
        tracking=True,
    )

    # ── Award Configuration ───────────────────────────────────────────────────
    award_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed Amount'),
            ('full', 'Full Scholarship'),
            ('custom', 'Custom'),
        ],
        string='Award Type',
        required=True,
        default='percentage',
        tracking=True,
    )
    default_percent = fields.Float(
        string='Default Percent',
        digits=(5, 2),
        help='Default percentage discount (used when award_type is percentage or full).',
    )
    default_amount = fields.Float(
        string='Default Amount',
        digits=(12, 2),
        help='Default fixed amount (used when award_type is fixed).',
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
        help=(
            'Which fee components this scholarship discounts.\n'
            '- Scholarship-Eligible: all fee lines where scholarship_allowed=True\n'
            '- Tuition Only: only fee lines with fee_type=tuition\n'
            '- Selected Fee Heads: specific fee heads chosen below'
        ),
    )
    fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        relation='edu_scholarship_scheme_fee_head_rel',
        column1='scheme_id',
        column2='fee_head_id',
        string='Applicable Fee Heads',
        help='Specific fee heads this scholarship applies to (when applies_on=selected_fee_heads).',
    )

    # ── Stacking / Exclusivity ────────────────────────────────────────────────
    allow_stacking = fields.Boolean(
        string='Allow Stacking',
        default=True,
        tracking=True,
        help='If True, this scholarship can be combined with other stackable scholarships.',
    )
    exclusive = fields.Boolean(
        string='Exclusive',
        default=False,
        tracking=True,
        help='If True, this scholarship cannot be combined with ANY other scholarship.',
    )
    stacking_group_id = fields.Many2one(
        comodel_name='edu.scholarship.stacking.group',
        string='Stacking Group',
        ondelete='set null',
        help='Optional grouping for stacking rule enforcement.',
    )
    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Lower number = higher priority. Used to determine calculation order.',
    )

    # ── Caps ──────────────────────────────────────────────────────────────────
    max_discount_percent = fields.Float(
        string='Max Discount %',
        digits=(5, 2),
        default=0.0,
        help='Maximum discount as percentage of eligible total. 0 = no cap.',
    )
    max_discount_amount = fields.Float(
        string='Max Discount Amount',
        digits=(12, 2),
        default=0.0,
        help='Maximum discount as fixed amount. 0 = no cap.',
    )

    # ── Misc ──────────────────────────────────────────────────────────────────
    renewable = fields.Boolean(
        string='Renewable',
        default=False,
        help='Whether this scholarship can be renewed for subsequent academic periods.',
    )
    requires_approval = fields.Boolean(
        string='Requires Approval',
        default=True,
        help='Whether scholarship awards require explicit approval before finalization.',
    )
    note = fields.Text(string='Notes')

    # ── Company ───────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

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
