from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_counselor = fields.Boolean(
        string='Is Counselor',
        default=False,
        help='When enabled, this employee can be assigned as a counselor on pre-admission leads.',
    )
