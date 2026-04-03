from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduAssessmentScheme(models.Model):
    """
    Master configuration for an assessment/result framework.

    A scheme defines the overall structure: what period it covers, which
    result system (percentage/GPA/both), which components contribute, and the
    promotion basis.  Schemes can be generic (no program/year) or scoped to a
    specific program, term, or academic year.
    """

    _inherit = ['edu.assessment.scheme', 'mail.thread', 'mail.activity.mixin']
    _description = 'Assessment Scheme'
    _order = 'name'
    _rec_name = 'name'

    # ── Identity ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Scheme Name', required=True, tracking=True,
    )
    code = fields.Char(
        string='Code', required=True, copy=False, index=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
        string='Status', default='draft', required=True,
        tracking=True,
    )
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ── Scope (all optional — allows generic reusable schemes) ────────────────
    program_id = fields.Many2one(
        'edu.program', string='Program', index=True,
        help='Leave blank for a scheme usable across all programs.',
    )
    academic_year_id = fields.Many2one(
        'edu.academic.year', string='Academic Year', index=True,
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Program Term', index=True,
        domain="[('program_id', '=', program_id)]",
    )

    # ── Result configuration ──────────────────────────────────────────────────
    result_period_type = fields.Selection(
        selection=[
            ('exam', 'Single Exam'),
            ('term', 'Term'),
            ('semester', 'Semester'),
            ('trimester', 'Trimester'),
            ('annual', 'Annual / Yearly'),
            ('cumulative_program', 'Cumulative Program'),
        ],
        string='Result Period', required=True, default='term', tracking=True,
    )
    result_system = fields.Selection(
        selection=[
            ('percentage', 'Percentage Only'),
            ('gpa', 'GPA Only'),
            ('both', 'Percentage + GPA'),
        ],
        string='Result System', required=True, default='percentage', tracking=True,
    )
    promotion_basis = fields.Selection(
        selection=[
            ('term_wise', 'Term-wise'),
            ('annual', 'Annual / Yearly'),
            ('cumulative', 'Cumulative'),
            ('final_only', 'Final Exam Only'),
        ],
        string='Promotion Basis', required=True, default='term_wise', tracking=True,
    )

    # ── Grace marks ───────────────────────────────────────────────────────────
    allow_grace_marks = fields.Boolean(string='Allow Grace Marks', tracking=True)
    grace_marks_limit = fields.Float(
        string='Grace Marks Limit', default=0.0,
        help='Maximum grace marks that can be awarded per subject.',
    )

    # ── Attendance rule ───────────────────────────────────────────────────────
    attendance_rule_enabled = fields.Boolean(
        string='Enforce Attendance Rule', tracking=True,
    )
    attendance_threshold_percent = fields.Float(
        string='Minimum Attendance %', default=75.0,
        help='Students below this threshold may be barred.',
    )

    # ── Source flags ──────────────────────────────────────────────────────────
    board_exam_included = fields.Boolean(string='Board Exam Included')
    internal_exam_included = fields.Boolean(
        string='Internal Exam Included', default=True,
    )
    continuous_assessment_included = fields.Boolean(
        string='Continuous Assessment Included', default=True,
    )

    # ── Back exam policy ──────────────────────────────────────────────────────
    back_exam_policy_id = fields.Many2one(
        'edu.back.exam.policy', string='Back Exam Policy',
    )

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'edu.assessment.scheme.line', 'scheme_id', string='Scheme Lines',
        copy=True,
    )
    line_count = fields.Integer(
        string='Lines', compute='_compute_line_count',
    )

    # ── Computed ──────────────────────────────────────────────────────────────
    total_weightage = fields.Float(
        string='Total Weightage %',
        compute='_compute_total_weightage', store=True,
        help='Sum of weightage_percent of all contributing lines.',
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.depends('line_ids.weightage_percent', 'line_ids.contributes_to_final')
    def _compute_total_weightage(self):
        for rec in self:
            rec.total_weightage = sum(
                l.weightage_percent
                for l in rec.line_ids
                if l.contributes_to_final
            )

    @api.constrains('grace_marks_limit')
    def _check_grace_marks(self):
        for rec in self:
            if rec.allow_grace_marks and rec.grace_marks_limit < 0:
                raise ValidationError('Grace marks limit cannot be negative.')

    @api.constrains('attendance_threshold_percent')
    def _check_attendance_threshold(self):
        for rec in self:
            if rec.attendance_rule_enabled:
                if not (0 < rec.attendance_threshold_percent <= 100):
                    raise ValidationError(
                        'Attendance threshold must be between 0 and 100.'
                    )

    def action_activate(self):
        for rec in self:
            rec.state = 'active'

    def action_archive_scheme(self):
        for rec in self:
            rec.state = 'archived'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_view_scheme_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Scheme Lines — {self.name}',
            'res_model': 'edu.assessment.scheme.line',
            'view_mode': 'list,form',
            'domain': [('scheme_id', '=', self.id)],
            'context': {'default_scheme_id': self.id},
        }

    _sql_constraints = [
        (
            'unique_code_company',
            'UNIQUE(code, company_id)',
            'Assessment scheme code must be unique per company.',
        ),
    ]


class EduAssessmentSchemeLine(models.Model):
    """
    One factor/component within an assessment scheme.

    Examples:
      - First Term Exam (20%), source: exam_session
      - Assignment Average (10%), source: assignment, aggregation: average
      - Attendance Score (10%), source: attendance
    """

    _inherit = 'edu.assessment.scheme.line'
    _description = 'Assessment Scheme Line'
    _order = 'scheme_id, sequence, id'

    scheme_id = fields.Many2one(
        'edu.assessment.scheme', string='Scheme',
        required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(string='Component Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    # ── Source configuration ──────────────────────────────────────────────────
    source_type = fields.Selection(
        selection=[
            ('exam_session', 'Exam Session'),
            ('exam_component', 'Exam Component'),
            ('assignment', 'Assignment'),
            ('attendance', 'Attendance'),
            ('class_test', 'Class Test'),
            ('class_performance', 'Class Performance'),
            ('project', 'Project'),
            ('practical', 'Practical'),
            ('viva', 'Viva / Oral'),
            ('manual', 'Manual Entry'),
            ('board_import', 'Board Marks Import'),
            ('custom', 'Custom'),
        ],
        string='Source Type', required=True, default='exam_session',
    )
    component_category = fields.Selection(
        selection=[
            ('internal_exam', 'Internal Exam'),
            ('terminal_exam', 'Terminal Exam'),
            ('final_exam', 'Final Exam'),
            ('board_exam', 'Board Exam'),
            ('assignment', 'Assignment'),
            ('attendance', 'Attendance'),
            ('project', 'Project'),
            ('performance', 'Class Performance'),
            ('custom', 'Custom'),
        ],
        string='Component Category',
    )

    # ── Source links (optional filters) ───────────────────────────────────────
    exam_session_ids = fields.Many2many(
        'edu.exam.session',
        'scheme_line_exam_session_rel',
        'scheme_line_id', 'exam_session_id',
        string='Linked Exam Sessions',
        help='If set, only these exam sessions are used as source for this line. '
             'If blank, any published session linked to this scheme line is used.',
    )
    assessment_category_ids = fields.Many2many(
        'edu.assessment.category',
        'scheme_line_assessment_category_rel',
        'scheme_line_id', 'category_id',
        string='Assessment Categories',
        help='Filter continuous assessment records by these categories.',
    )
    exam_attempt_type = fields.Selection(
        selection=[
            ('regular', 'Regular'),
            ('back', 'Back Exam'),
            ('makeup', 'Make-up'),
            ('improvement', 'Improvement'),
            ('special', 'Special'),
        ],
        string='Exam Attempt Type', default='regular',
    )

    # ── Aggregation ───────────────────────────────────────────────────────────
    aggregation_method = fields.Selection(
        selection=[
            ('total', 'Sum / Total'),
            ('average', 'Average'),
            ('best', 'Best of N'),
            ('latest', 'Latest Record'),
            ('weighted_average', 'Weighted Average'),
            ('manual', 'Manual'),
        ],
        string='Aggregation Method', required=True, default='total',
    )
    best_of_count = fields.Integer(
        string='Best of N',
        help='Take the best N scores when aggregation_method is "best".',
    )
    drop_lowest = fields.Integer(
        string='Drop Lowest N',
        help='Drop N lowest scores before aggregating.',
    )
    group_key = fields.Char(
        string='Group Key',
        help='Optional group label for combining multiple lines (e.g. "internal_total").',
    )

    # ── Marks configuration ───────────────────────────────────────────────────
    max_marks = fields.Float(
        string='Max Marks (Normalized)', required=True, default=100.0,
        help='After aggregation, source values are normalized to this scale.',
    )
    pass_marks = fields.Float(
        string='Pass Marks', default=0.0,
        help='Minimum marks required to pass this component (if separate pass is enforced).',
    )
    weightage_percent = fields.Float(
        string='Weightage %', required=True, default=0.0,
        help='Percentage contribution to the final result (all contributing lines should sum to 100).',
    )

    # ── Pass / contribution rules ──────────────────────────────────────────────
    is_mandatory = fields.Boolean(
        string='Mandatory', default=False,
        help='Failing this component auto-fails the subject if requires_separate_pass is also set.',
    )
    requires_separate_pass = fields.Boolean(
        string='Requires Separate Pass', default=False,
        help='Student must individually pass this component.',
    )
    contributes_to_final = fields.Boolean(
        string='Contributes to Final', default=True,
        help='Include this line in weighted final result computation.',
    )
    include_in_gpa = fields.Boolean(
        string='Include in GPA', default=True,
    )
    include_in_percentage = fields.Boolean(
        string='Include in Percentage', default=True,
    )
    is_external = fields.Boolean(
        string='External / Board', default=False,
        help='Marks come from an external board; handled as board_import.',
    )
    is_board_component = fields.Boolean(string='Board Component')

    linked_exam_type = fields.Char(
        string='Linked Exam Type Tag',
        help='Free-text tag for cross-referencing this line with exam sessions.',
    )
    note = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('pass_marks', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if rec.max_marks <= 0:
                raise ValidationError(
                    f'Max marks must be positive on line "{rec.name}".'
                )
            if rec.pass_marks < 0 or rec.pass_marks > rec.max_marks:
                raise ValidationError(
                    f'Pass marks on "{rec.name}" must be between 0 and {rec.max_marks}.'
                )

    @api.constrains('weightage_percent')
    def _check_weightage(self):
        for rec in self:
            if rec.weightage_percent < 0 or rec.weightage_percent > 100:
                raise ValidationError(
                    f'Weightage percent on "{rec.name}" must be between 0 and 100.'
                )

    @api.constrains('best_of_count', 'drop_lowest')
    def _check_best_drop(self):
        for rec in self:
            if rec.best_of_count < 0:
                raise ValidationError('Best of N cannot be negative.')
            if rec.drop_lowest < 0:
                raise ValidationError('Drop lowest N cannot be negative.')
