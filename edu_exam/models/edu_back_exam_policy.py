import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduBackExamPolicy(models.Model):
    """Back Exam Policy — governs how many back/makeup/improvement/special
    attempts a student is allowed and whether attendance is a prerequisite.
    Attach a policy to an exam session to enforce these rules during back-exam
    generation.
    """

    _name = 'edu.back.exam.policy'
    _description = 'Back Exam Policy'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Policy Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
    )
    max_back_attempts = fields.Integer(
        string='Max Back Attempts',
        default=3,
        help='Maximum number of back exam attempts permitted per subject.',
    )
    max_makeup_attempts = fields.Integer(
        string='Max Makeup Attempts',
        default=1,
        help='Maximum number of makeup exam attempts permitted per subject.',
    )
    max_improvement_attempts = fields.Integer(
        string='Max Improvement Attempts',
        default=1,
        help='Maximum number of improvement exam attempts permitted per subject.',
    )
    allow_back = fields.Boolean(
        string='Allow Back Exam',
        default=True,
    )
    allow_makeup = fields.Boolean(
        string='Allow Makeup Exam',
        default=False,
    )
    allow_improvement = fields.Boolean(
        string='Allow Improvement Exam',
        default=False,
    )
    allow_special = fields.Boolean(
        string='Allow Special Exam',
        default=False,
    )
    min_attendance_for_back = fields.Float(
        string='Min Attendance % for Back Exam',
        default=0.0,
        help=(
            'Minimum attendance percentage required to sit a back exam. '
            'Set to 0 to disable the attendance requirement.'
        ),
    )
    description = fields.Text(
        string='Description',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

