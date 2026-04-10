from odoo import fields, models


class EduStaffQualification(models.Model):
    _name = 'edu.staff.qualification'
    _description = 'Staff Qualification'
    _order = 'year_of_completion desc, degree'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    degree = fields.Char(
        string='Degree',
        required=True,
        help='e.g. B.Ed, M.Sc Physics, PhD Mathematics',
    )
    institution = fields.Char(
        string='Institution',
        help='e.g. Tribhuvan University',
    )
    year_of_completion = fields.Integer(
        string='Year',
        help='Year of completion, e.g. 2020',
    )
    notes = fields.Text(
        string='Notes',
    )
