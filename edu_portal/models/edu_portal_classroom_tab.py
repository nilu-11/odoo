"""Portal classroom tab registry.

Seeded via portal_classroom_tabs_data.xml with 12 records — 6 built-in
tabs (stream, attendance, exams, assessments, results, people) times
2 roles (teacher, student). Read once per request by
controllers/helpers.py::_resolve_portal_registry.
"""
from odoo import fields, models


class EduPortalClassroomTab(models.Model):
    _name = 'edu.portal.classroom.tab'
    _description = 'Portal Classroom Tab'
    _order = 'sequence, id'

    # ═══ Identity / Core ═══
    key = fields.Char(
        string='Key',
        required=True,
        help=(
            "Stable identifier used for active-tab highlighting. "
            "Built-ins: stream, attendance, exams, assessments, results, people."
        ),
    )
    label = fields.Char(
        string='Label',
        required=True,
        translate=True,
    )
    icon = fields.Char(
        string='Icon',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    route_pattern = fields.Char(
        string='Route Pattern',
        required=True,
        help=(
            "Route template with a {classroom_id} placeholder. "
            "Example: /portal/teacher/classroom/{classroom_id}/stream"
        ),
    )

    # ═══ Scope ═══
    role = fields.Selection(
        selection=[
            ('teacher', 'Teacher'),
            ('student', 'Student'),
            ('all',     'All'),
        ],
        string='Role',
        required=True,
        default='all',
    )
    active = fields.Boolean(default=True)

    # ═══ Dynamic resolution ═══
    visibility_method = fields.Char(
        string='Visibility Method',
        help=(
            "Optional dotted path 'model.method'. Receives the classroom, "
            "user, and role; must return bool. Silently skipped if "
            "model/method missing."
        ),
    )

    _sql_constraints = [
        ('uniq_key_role',
         'UNIQUE(key, role)',
         'Classroom tab key must be unique per role.'),
    ]
