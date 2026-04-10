from odoo import fields, models


class EduExamPaper(models.Model):
    _inherit = 'edu.exam.paper'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        domain=[('is_teaching_staff', '=', True)],
        help='Teaching staff member responsible for this exam paper.',
    )
