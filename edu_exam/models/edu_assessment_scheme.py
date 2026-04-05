import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exam type and attempt type selections — shared across the module
# ---------------------------------------------------------------------------
EXAM_TYPE_SELECTION = [
    ('internal', 'Internal'),
    ('terminal', 'Terminal'),
    ('midterm', 'Midterm'),
    ('final', 'Final'),
    ('board', 'Board'),
    ('practical', 'Practical'),
    ('viva', 'Viva'),
    ('assignment_based', 'Assignment Based'),
    ('project_based', 'Project Based'),
    ('custom', 'Custom'),
]

ATTEMPT_TYPE_SELECTION = [
    ('regular', 'Regular'),
    ('back', 'Back'),
    ('makeup', 'Makeup'),
    ('improvement', 'Improvement'),
    ('special', 'Special'),
]


class EduAssessmentScheme(models.Model):
    """Assessment Scheme — defines how marks from multiple exam components
    are weighted to produce a final result.  Exam sessions reference a scheme
    (and optionally a specific scheme line) so that the result module can
    aggregate marks correctly.
    """

    _name = 'edu.assessment.scheme'
    _description = 'Assessment Scheme'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Scheme Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
    )
    description = fields.Text(
        string='Description',
    )
    note = fields.Text(
        string='Notes',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    line_ids = fields.One2many(
        comodel_name='edu.assessment.scheme.line',
        inverse_name='scheme_id',
        string='Scheme Lines',
    )



class EduAssessmentSchemeLine(models.Model):
    """One component line within an assessment scheme (e.g. Midterm 30%,
    Final 70%).  Each line can optionally map to an exam_type and attempt_type
    so that the result aggregation engine knows which session contributes what.
    """

    _name = 'edu.assessment.scheme.line'
    _description = 'Assessment Scheme Line'
    _order = 'scheme_id, sequence, name'
    _rec_name = 'name'

    scheme_id = fields.Many2one(
        comodel_name='edu.assessment.scheme',
        string='Scheme',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(
        string='Component Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
    )
    exam_type = fields.Selection(
        selection=EXAM_TYPE_SELECTION,
        string='Exam Type',
    )
    attempt_type = fields.Selection(
        selection=ATTEMPT_TYPE_SELECTION,
        string='Attempt Type',
    )
    weightage_percent = fields.Float(
        string='Weightage (%)',
        default=0.0,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )


class EduResultSession(models.Model):
    """Result Session — stub for forward reference by edu_result.
    This model aggregates exam session results into a publishable result set.
    The full implementation lives in edu_result; this stub enables clean M2O
    references from edu_exam without a circular dependency.
    """

    _name = 'edu.result.session'
    _description = 'Result Session (extended by edu_result)'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        ondelete='restrict',
    )
    exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Exam Session',
        ondelete='set null',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='draft',
        required=True,
    )
    note = fields.Text(
        string='Note',
    )


class EduResultMarksheet(models.Model):
    """Result Marksheet — stub for back-exam backlog origin reference.
    Full implementation lives in edu_result.
    """

    _name = 'edu.result.marksheet'
    _description = 'Result Marksheet (extended by edu_result)'
    _order = 'student_id, subject_id'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
    )
    result_session_id = fields.Many2one(
        comodel_name='edu.result.session',
        string='Result Session',
        ondelete='cascade',
        index=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        ondelete='restrict',
    )
    final_marks = fields.Float(
        string='Final Marks',
        default=0.0,
    )
    is_pass = fields.Boolean(
        string='Pass',
        default=False,
    )

    @api.depends('student_id', 'subject_id')
    def _compute_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            subject = rec.subject_id.name or ''
            rec.name = f'{student} — {subject}' if student or subject else 'New'
