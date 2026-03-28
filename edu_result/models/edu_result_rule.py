from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduResultRule(models.Model):
    """
    Pass/fail, publication, and withhold logic rules.

    A result rule is attached to a result session and governs how the engine
    determines final subject and student-level outcomes.
    """

    _name = 'edu.result.rule'
    _description = 'Result Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Rule Name', required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
        string='Status', default='draft', required=True, tracking=True,
    )
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    # ── Scheme links ──────────────────────────────────────────────────────────
    scheme_id = fields.Many2one(
        'edu.assessment.scheme', string='Assessment Scheme',
        help='Associate this rule with a specific scheme for filtering.',
    )
    grading_scheme_id = fields.Many2one(
        'edu.grading.scheme', string='Grading Scheme',
    )

    # ── Component pass rules ──────────────────────────────────────────────────
    fail_on_any_mandatory_component = fields.Boolean(
        string='Fail on Any Mandatory Component Fail',
        default=True,
        tracking=True,
        help='If any mandatory scheme line is not individually passed, the '
             'subject is marked as failed regardless of the total.',
    )
    use_component_wise_pass = fields.Boolean(
        string='Component-wise Pass Required',
        default=False,
        tracking=True,
        help='Every scheme line that has requires_separate_pass=True must '
             'individually be passed.',
    )
    use_weighted_total = fields.Boolean(
        string='Use Weighted Total for Pass Decision',
        default=True,
    )

    # ── Overall thresholds ─────────────────────────────────────────────────────
    minimum_overall_percent = fields.Float(
        string='Minimum Overall %', default=40.0, tracking=True,
        help='Student must achieve at least this percentage in a subject to pass.',
    )
    minimum_overall_gpa = fields.Float(
        string='Minimum Overall GPA', default=0.0,
        help='Minimum GPA required (when result_system includes GPA).',
    )

    # ── Backlog ───────────────────────────────────────────────────────────────
    allow_backlog = fields.Boolean(
        string='Allow Backlog / Promotion with Fail', default=True, tracking=True,
        help='If True, a student can be promoted even with some failed subjects (backlogs).',
    )
    max_backlog_subjects = fields.Integer(
        string='Max Backlog Subjects Allowed', default=3,
        help='Maximum number of subjects a student can fail and still be promoted.',
    )

    # ── Combined internal/external ─────────────────────────────────────────────
    combine_internal_and_external = fields.Boolean(
        string='Combined Internal + External Pass',
        default=False,
        help='Both internal and external components must be passed individually.',
    )

    # ── Action on special conditions ─────────────────────────────────────────
    attendance_shortage_action = fields.Selection(
        selection=[
            ('ignore', 'Ignore'),
            ('warn', 'Warn Only'),
            ('withhold', 'Withhold Result'),
            ('fail', 'Mark as Fail'),
            ('block', 'Block from Appearing'),
        ],
        string='Attendance Shortage Action',
        default='warn', tracking=True,
    )
    fee_due_action = fields.Selection(
        selection=[
            ('ignore', 'Ignore'),
            ('warn', 'Warn Only'),
            ('withhold', 'Withhold Result'),
        ],
        string='Fee Due Action', default='ignore', tracking=True,
    )
    malpractice_action = fields.Selection(
        selection=[
            ('fail_component', 'Fail Component Only'),
            ('fail_subject', 'Fail Subject'),
            ('withhold_result', 'Withhold Entire Result'),
        ],
        string='Malpractice Action', default='fail_subject', tracking=True,
    )

    # ── Result status basis ───────────────────────────────────────────────────
    result_status_basis = fields.Selection(
        selection=[
            ('marks_only', 'Marks Only'),
            ('weighted_total', 'Weighted Total'),
            ('gpa', 'GPA'),
            ('percentage_and_component_pass', 'Percentage + Component Pass'),
        ],
        string='Result Status Basis',
        default='percentage_and_component_pass', tracking=True,
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('minimum_overall_percent')
    def _check_min_percent(self):
        for rec in self:
            if not (0.0 <= rec.minimum_overall_percent <= 100.0):
                raise ValidationError(
                    'Minimum overall percentage must be between 0 and 100.'
                )

    @api.constrains('max_backlog_subjects')
    def _check_max_backlog(self):
        for rec in self:
            if rec.max_backlog_subjects < 0:
                raise ValidationError(
                    'Max backlog subjects allowed cannot be negative.'
                )

    def action_activate(self):
        self.write({'state': 'active'})

    def action_archive_rule(self):
        self.write({'state': 'archived'})
