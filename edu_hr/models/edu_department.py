from odoo import fields, models


class EduDepartment(models.Model):
    _inherit = 'edu.department'

    hr_department_id = fields.Many2one(
        comodel_name='hr.department',
        string='HR Department',
        ondelete='set null',
        help='Optional link to the corresponding HR organizational department.',
    )
