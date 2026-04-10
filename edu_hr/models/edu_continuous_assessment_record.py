from odoo import fields, models


class EduContinuousAssessmentRecord(models.Model):
    _inherit = 'edu.continuous.assessment.record'

    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        index=True,
        tracking=True,
        domain=[('is_teaching_staff', '=', True)],
        help='Teaching staff member who conducted this assessment.',
    )
