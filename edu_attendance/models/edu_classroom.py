from odoo import fields, models


class EduClassroomAttendance(models.Model):
    """Inject attendance_register_id into edu.classroom."""

    _inherit = 'edu.classroom'

    attendance_register_id = fields.Many2one(
        comodel_name='edu.attendance.register',
        string='Attendance Register',
        ondelete='set null',
        copy=False,
        index=True,
        readonly=True,
        help=(
            'The attendance register linked to this classroom. '
            'Created automatically when the classroom is activated.'
        ),
    )
