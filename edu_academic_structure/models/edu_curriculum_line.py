from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduCurriculumLine(models.Model):
    _name = 'edu.curriculum.line'
    _description = 'Curriculum Line — Subject mapped to a Program Term'
    _order = 'program_term_id, sequence'
    _rec_name = 'subject_id'

    # ── Core FK — single link to the bridge model ────────────────────────────────
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        required=True,
        ondelete='cascade',
        index=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        required=True,
        ondelete='restrict',
        index=True,
    )
    subject_category = fields.Selection(
        selection=[
            ('compulsory', 'Compulsory'),
            ('elective', 'Elective'),
            ('optional', 'Optional'),
        ],
        string='Subject Category',
        required=True,
        default='compulsory',
    )
    credit_hours = fields.Float(
        string='Credit Hours',
        digits=(5, 1),
    )
    full_marks = fields.Float(
        string='Full Marks',
        digits=(10, 2),
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        digits=(10, 2),
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    # ── Related convenience fields (stored for search / group / report) ──────────
    program_id = fields.Many2one(
        related='program_term_id.program_id',
        string='Program',
        store=True,
        index=True,
    )
    progression_no = fields.Integer(
        related='program_term_id.progression_no',
        string='Progression No.',
        store=True,
    )
    subject_type = fields.Selection(
        related='subject_id.subject_type',
        string='Subject Type',
        store=True,
    )
    department_id = fields.Many2one(
        related='program_term_id.department_id',
        string='Department',
        store=True,
    )
    company_id = fields.Many2one(
        related='program_term_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── SQL constraints ──────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'subject_program_term_unique',
            'UNIQUE(program_term_id, subject_id)',
            'A subject can only appear once per program term.',
        ),
    ]

    # ── On subject change: copy default marks and credits ────────────────────────
    @api.onchange('subject_id')
    def _onchange_subject_id(self):
        if self.subject_id:
            self.credit_hours = self.subject_id.credit_hours
            self.full_marks = self.subject_id.full_marks
            self.pass_marks = self.subject_id.pass_marks

    # ── Python constraints ───────────────────────────────────────────────────────
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
