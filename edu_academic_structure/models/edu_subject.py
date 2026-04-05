from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduSubject(models.Model):
    _name = 'edu.subject'
    _description = 'Subject Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'department_id, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Subject Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Subject Code',
        required=True,
        tracking=True,
        index=True,
        help='Unique subject code, e.g. CS101, MATH201',
    )
    department_id = fields.Many2one(
        comodel_name='edu.department',
        string='Department',
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Owning department. Optional — some subjects may be cross-departmental.',
    )
    subject_type = fields.Selection(
        selection=[
            ('theory', 'Theory'),
            ('practical_theory', 'Practical & Theory'),
            ('simulation', 'Simulation'),
            ('project', 'Project'),
        ],
        string='Subject Type',
        required=True,
        default='theory',
        tracking=True,
    )
    credit_hours = fields.Float(
        string='Credit Hours',
        default=3.0,
        digits=(5, 1),
    )
    full_marks = fields.Float(
        string='Full Marks',
        default=100.0,
        digits=(10, 2),
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        default=40.0,
        digits=(10, 2),
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

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Subject code must be unique per company.'),
    ]

    @api.constrains('pass_marks', 'full_marks')
    def _check_marks(self):
        for rec in self:
            if rec.full_marks < 0:
                raise ValidationError('Full marks cannot be negative.')
            if rec.pass_marks < 0:
                raise ValidationError('Pass marks cannot be negative.')
            if rec.pass_marks > rec.full_marks:
                raise ValidationError(
                    f'Pass marks ({rec.pass_marks}) cannot exceed full marks ({rec.full_marks}).'
                )

    @api.constrains('credit_hours')
    def _check_credit_hours(self):
        for rec in self:
            if rec.credit_hours < 0:
                raise ValidationError('Credit hours cannot be negative.')

    def unlink(self):
        for rec in self:
            cl_count = self.env['edu.curriculum.line'].search_count([
                ('subject_id', '=', rec.id),
            ])
            if cl_count:
                raise UserError(
                    f'Cannot delete subject "{rec.name}" — '
                    f'it is used in {cl_count} curriculum line(s). Archive it instead.'
                )
        return super().unlink()
