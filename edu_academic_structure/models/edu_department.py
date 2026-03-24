from odoo import api, fields, models
from odoo.exceptions import UserError


class EduDepartment(models.Model):
    _name = 'edu.department'
    _description = 'Academic Department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='Department Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Unique department code, e.g. CS, BBA, ENG',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    program_ids = fields.One2many(
        comodel_name='edu.program',
        inverse_name='department_id',
        string='Programs',
    )
    program_count = fields.Integer(
        string='Programs',
        compute='_compute_program_count',
        store=True,
    )

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Department code must be unique per company.'),
        ('name_company_unique', 'UNIQUE(name, company_id)',
         'Department name must be unique per company.'),
    ]

    @api.depends('program_ids')
    def _compute_program_count(self):
        data = self.env['edu.program']._read_group(
            [('department_id', 'in', self.ids)],
            ['department_id'],
            ['__count'],
        )
        mapped = {dept.id: count for dept, count in data}
        for rec in self:
            rec.program_count = mapped.get(rec.id, 0)

    def unlink(self):
        for rec in self:
            if rec.program_ids:
                raise UserError(
                    f'Cannot delete department "{rec.name}" — '
                    f'it has {len(rec.program_ids)} program(s). Archive it instead.'
                )
        return super().unlink()

    def action_view_programs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Programs — {self.name}',
            'res_model': 'edu.program',
            'view_mode': 'list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id},
        }
