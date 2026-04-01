from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduProgram(models.Model):
    _name = 'edu.program'
    _description = 'Academic Program'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'department_id, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Program Name',
        required=True,
        tracking=True,
        help='E.g. Bachelor of Computer Science',
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Unique program code, e.g. BCS, MBA, BCOM',
    )
    department_id = fields.Many2one(
        comodel_name='edu.department',
        string='Department',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    program_type = fields.Selection(
        selection=[
            ('undergraduate', 'Undergraduate'),
            ('postgraduate', 'Postgraduate'),
            ('diploma', 'Diploma'),
            ('certificate', 'Certificate'),
            ('doctorate', 'Doctorate'),
            ('other', 'Other'),
        ],
        string='Program Type',
        required=True,
        default='undergraduate',
        tracking=True,
    )
    duration_value = fields.Integer(
        string='Duration',
        required=True,
        default=4,
        help='Numeric duration value, e.g. 4',
    )
    duration_unit = fields.Selection(
        selection=[
            ('years', 'Years'),
            ('months', 'Months'),
            ('semesters', 'Semesters'),
            ('terms', 'Terms'),
        ],
        string='Duration Unit',
        required=True,
        default='years',
    )
    total_terms = fields.Integer(
        string='Total Progressions',
        required=True,
        default=8,
        help='Total number of progression stages (semesters/quarters/etc.) in this program.',
    )
    term_system = fields.Selection(
        selection=[
            ('semester', 'Semester'),
            ('trimester', 'Trimester'),
            ('quarter', 'Quarter'),
            ('annual', 'Annual'),
            ('custom', 'Custom'),
        ],
        string='Term System',
        required=True,
        default='semester',
        tracking=True,
        help='Determines naming convention for program progression stages.',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        related='department_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    batch_ids = fields.One2many(
        comodel_name='edu.batch',
        inverse_name='program_id',
        string='Batches',
    )
    batch_count = fields.Integer(
        string='Batches',
        compute='_compute_batch_count',
        store=True,
    )
    program_term_ids = fields.One2many(
        comodel_name='edu.program.term',
        inverse_name='program_id',
        string='Program Terms',
    )
    program_term_count = fields.Integer(
        string='Program Terms',
        compute='_compute_program_term_count',
        store=True,
    )
    curriculum_line_ids = fields.One2many(
        comodel_name='edu.curriculum.line',
        inverse_name='program_id',
        string='Curriculum',
    )
    curriculum_count = fields.Integer(
        string='Curriculum Lines',
        compute='_compute_curriculum_count',
        store=True,
    )

    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Program code must be unique per company.'),
    ]

    @api.constrains('duration_value')
    def _check_duration(self):
        for rec in self:
            if rec.duration_value <= 0:
                raise ValidationError('Duration must be a positive number.')

    @api.constrains('total_terms')
    def _check_total_terms(self):
        for rec in self:
            if rec.total_terms <= 0:
                raise ValidationError('Total terms must be a positive number.')

    @api.depends('batch_ids')
    def _compute_batch_count(self):
        data = self.env['edu.batch']._read_group(
            [('program_id', 'in', self.ids)],
            ['program_id'],
            ['__count'],
        )
        mapped = {prog.id: count for prog, count in data}
        for rec in self:
            rec.batch_count = mapped.get(rec.id, 0)

    @api.depends('program_term_ids')
    def _compute_program_term_count(self):
        data = self.env['edu.program.term']._read_group(
            [('program_id', 'in', self.ids)],
            ['program_id'],
            ['__count'],
        )
        mapped = {prog.id: count for prog, count in data}
        for rec in self:
            rec.program_term_count = mapped.get(rec.id, 0)

    @api.depends('curriculum_line_ids')
    def _compute_curriculum_count(self):
        data = self.env['edu.curriculum.line']._read_group(
            [('program_id', 'in', self.ids)],
            ['program_id'],
            ['__count'],
        )
        mapped = {prog.id: count for prog, count in data}
        for rec in self:
            rec.curriculum_count = mapped.get(rec.id, 0)

    def unlink(self):
        for rec in self:
            if rec.batch_ids:
                raise UserError(
                    f'Cannot delete program "{rec.name}" — '
                    f'it has {len(rec.batch_ids)} batch(es). Archive it instead.'
                )
            if rec.program_term_ids:
                raise UserError(
                    f'Cannot delete program "{rec.name}" — '
                    f'it has {len(rec.program_term_ids)} program term(s). '
                    'Archive it instead.'
                )
        return super().unlink()

    # ═════════════════════════════════════════════════════════════════════════
    # Generate Program Terms
    # ═════════════════════════════════════════════════════════════════════════
    def action_generate_program_terms(self):
        """
        Auto-create missing program term records from 1 to total_terms.

        - Does not duplicate existing terms (by progression_no)
        - Does not delete existing terms
        - Only creates missing gaps
        """
        self.ensure_one()
        if self.total_terms <= 0:
            raise UserError(
                f'Cannot generate program terms — '
                f'total progressions for "{self.name}" must be greater than zero.'
            )
        if not self.term_system:
            raise UserError(
                f'Cannot generate program terms — '
                f'set the Term System on "{self.name}" first.'
            )

        ProgramTerm = self.env['edu.program.term']
        existing_nos = set(
            ProgramTerm.search([
                ('program_id', '=', self.id),
            ]).mapped('progression_no')
        )

        to_create = []
        for n in range(1, self.total_terms + 1):
            if n in existing_nos:
                continue
            to_create.append({
                'program_id': self.id,
                'progression_no': n,
                'sequence': n * 10,
            })

        if not to_create:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No New Terms',
                    'message': (
                        f'All {self.total_terms} program terms already exist '
                        f'for "{self.name}".'
                    ),
                    'type': 'info',
                    'sticky': False,
                },
            }

        ProgramTerm.create(to_create)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Program Terms Generated',
                'message': (
                    f'Created {len(to_create)} program term(s) for "{self.name}". '
                    f'Total: {self.total_terms}.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_batches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Batches — {self.name}',
            'res_model': 'edu.batch',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }

    def action_view_program_terms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Program Terms — {self.name}',
            'res_model': 'edu.program.term',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id},
        }

    def action_view_curriculum(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Curriculum — {self.name}',
            'res_model': 'edu.curriculum.line',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {},
        }
