from odoo import fields, models


class EduClassroom(models.Model):
    _inherit = 'edu.classroom'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        index=True,
        domain=[('is_teaching_staff', '=', True)],
        help='Teaching staff member responsible for this classroom.',
    )
