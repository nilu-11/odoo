import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

COMPONENT_TYPE_SELECTION = [
    ('theory', 'Theory'),
    ('practical', 'Practical'),
    ('viva', 'Viva'),
    ('oral', 'Oral'),
    ('project', 'Project'),
    ('assignment', 'Assignment'),
    ('custom', 'Custom'),
]


class EduExamPaperComponent(models.Model):
    """Paper Component — splits an exam paper into sub-components
    (e.g. Theory 70 marks + Practical 30 marks = 100 marks total).

    When paper components are defined, each student marksheet will have a
    corresponding edu.exam.marksheet.component record for granular marks capture.
    """

    _name = 'edu.exam.paper.component'
    _description = 'Exam Paper Component'
    _order = 'exam_paper_id, sequence, name'
    _rec_name = 'name'

    exam_paper_id = fields.Many2one(
        comodel_name='edu.exam.paper',
        string='Exam Paper',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(
        string='Component Name',
        required=True,
    )
    component_type = fields.Selection(
        selection=COMPONENT_TYPE_SELECTION,
        string='Type',
        required=True,
        default='theory',
    )
    max_marks = fields.Float(
        string='Max Marks',
        required=True,
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        required=True,
    )
    weightage_percent = fields.Float(
        string='Weightage (%)',
        default=100.0,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='If unchecked, absence from this component does not fail the paper.',
    )
    note = fields.Char(
        string='Note',
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_paper_component_name',
            'UNIQUE(exam_paper_id, name)',
            'Component name must be unique within the exam paper.',
        ),
        (
            'check_pass_le_max',
            'CHECK(pass_marks <= max_marks)',
            'Pass marks cannot exceed max marks for a component.',
        ),
        (
            'check_max_marks_positive',
            'CHECK(max_marks > 0)',
            'Component max marks must be greater than zero.',
        ),
    ]
