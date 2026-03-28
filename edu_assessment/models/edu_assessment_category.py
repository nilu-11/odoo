from odoo import fields, models

# ---------------------------------------------------------------------------
# Category type selection — shared constant used across the module
# ---------------------------------------------------------------------------
CATEGORY_TYPE_SELECTION = [
    ('assignment', 'Assignment'),
    ('class_test', 'Class Test'),
    ('project', 'Project'),
    ('practical_continuous', 'Practical / Continuous'),
    ('class_performance', 'Class Performance'),
    ('participation', 'Participation'),
    ('attendance_score', 'Attendance Score'),
    ('observation', 'Observation'),
    ('manual', 'Manual / Internal'),
    ('custom', 'Custom'),
]


class EduAssessmentCategory(models.Model):
    """Master configuration for continuous assessment categories.

    Institutions configure which assessment types they use (e.g. Assignment,
    Class Test, Attendance Score) and set default marks.  The result engine
    (edu_result) will later pick up categories flagged as contributing to the
    final result.
    """

    _name = 'edu.assessment.category'
    _description = 'Assessment Category'
    _order = 'sequence, name'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Category Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
        help='Short code for the category (e.g. ASGN, CT, PROJ).',
    )
    category_type = fields.Selection(
        selection=CATEGORY_TYPE_SELECTION,
        string='Category Type',
        required=True,
        default='custom',
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # ── Defaults ──────────────────────────────────────────────────────────────

    default_max_marks = fields.Float(
        string='Default Max Marks',
        default=100.0,
        help='Default maximum marks when creating new assessment records for this category.',
    )
    contributes_to_result = fields.Boolean(
        string='Contributes to Result',
        default=True,
        help='When True, edu_result will include records of this category in final result computation.',
    )

    # ── Other ─────────────────────────────────────────────────────────────────

    note = fields.Text(
        string='Description / Notes',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_code_company',
            'UNIQUE(code, company_id)',
            'Assessment category code must be unique per company.',
        ),
    ]
