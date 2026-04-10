from odoo import fields, models


class EduAttendanceRegister(models.Model):
    _inherit = 'edu.attendance.register'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        related='classroom_id.teacher_id',
        store=True,
        index=True,
    )
