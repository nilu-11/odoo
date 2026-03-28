from odoo import fields, models, _


class EduStudentAttendance(models.Model):
    """Add attendance smart-button count to edu.student."""

    _inherit = 'edu.student'

    attendance_line_count = fields.Integer(
        string='Attendance Sessions',
        compute='_compute_attendance_line_count',
        store=False,
    )

    def _compute_attendance_line_count(self):
        data = self.env['edu.attendance.sheet.line']._read_group(
            domain=[('student_id', 'in', self.ids)],
            groupby=['student_id'],
            aggregates=['__count'],
        )
        mapped = {student.id: count for student, count in data}
        for rec in self:
            rec.attendance_line_count = mapped.get(rec.id, 0)

    def action_view_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance — %s') % self.display_name,
            'res_model': 'edu.attendance.sheet.line',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {},
        }
