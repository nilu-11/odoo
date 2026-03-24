from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduProgramTerm(models.Model):
    """
    Program Term — reusable progression template for a program.

    Each record represents one stage in a program's progression sequence
    (e.g. "Semester 1", "Semester 2", ..., "Semester 8" for a 4-year BCS).

    These are created once per program and reused across all batches/intakes.
    Academic year belongs to the Batch, not here.
    """

    _name = 'edu.program.term'
    _description = 'Program Term — reusable progression template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'program_id, progression_no'
    _rec_name = 'name'

    # ── Computed identity ────────────────────────────────────────────────────────
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        readonly=False,
        help='Auto-computed from program term system and progression number. Editable.',
    )
    code = fields.Char(
        string='Code',
        compute='_compute_code',
        store=True,
        readonly=False,
        help='Auto-computed from program code and progression number. Editable.',
    )

    # ── Core fields ──────────────────────────────────────────────────────────────
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    progression_no = fields.Integer(
        string='Progression No.',
        required=True,
        tracking=True,
        help='Sequential progression number within the program (e.g. 1, 2, 3 ... N).',
    )
    progression_label = fields.Char(
        string='Progression Label',
        compute='_compute_progression_label',
        store=True,
        readonly=False,
        help='Auto-computed but editable. E.g. "Semester 1", "Term 3".',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(default=True)
    is_final_progression = fields.Boolean(
        string='Final Progression?',
        compute='_compute_is_final_progression',
        store=True,
        help='True when this is the last progression stage of the program.',
    )
    notes = fields.Text(string='Notes')

    # ── Related / stored for reporting & security ────────────────────────────────
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='program_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Reverse relations ────────────────────────────────────────────────────────
    curriculum_line_ids = fields.One2many(
        comodel_name='edu.curriculum.line',
        inverse_name='program_term_id',
        string='Curriculum Lines',
    )
    curriculum_count = fields.Integer(
        string='Subjects',
        compute='_compute_curriculum_count',
        store=True,
    )

    # ── SQL constraints ─────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'program_progression_unique',
            'UNIQUE(program_id, progression_no)',
            'Each progression number must be unique within a program.',
        ),
        (
            'progression_positive',
            'CHECK(progression_no > 0)',
            'Progression number must be positive.',
        ),
    ]

    # ── Progression label mapping ────────────────────────────────────────────────
    _TERM_SYSTEM_LABELS = {
        'semester': 'Semester',
        'trimester': 'Trimester',
        'quarter': 'Quarter',
        'annual': 'Year',
        'custom': 'Stage',
    }

    # ── Computed fields ──────────────────────────────────────────────────────────
    @api.depends('program_id.name', 'progression_no', 'program_id.term_system')
    def _compute_name(self):
        for rec in self:
            if rec.program_id and rec.progression_no:
                label = self._TERM_SYSTEM_LABELS.get(
                    rec.program_id.term_system, 'Stage'
                )
                rec.name = f'{rec.program_id.name} — {label} {rec.progression_no}'
            else:
                rec.name = False

    @api.depends('program_id.code', 'progression_no', 'program_id.term_system')
    def _compute_code(self):
        # Short prefix map for codes
        _PREFIX = {
            'semester': 'SEM',
            'trimester': 'TRI',
            'quarter': 'QTR',
            'annual': 'YR',
            'custom': 'STG',
        }
        for rec in self:
            if rec.program_id and rec.progression_no:
                prefix = _PREFIX.get(rec.program_id.term_system, 'STG')
                rec.code = (
                    f'{rec.program_id.code}-{prefix}-'
                    f'{rec.progression_no:02d}'
                )
            else:
                rec.code = False

    @api.depends('progression_no', 'program_id.term_system')
    def _compute_progression_label(self):
        for rec in self:
            if rec.progression_no:
                label = self._TERM_SYSTEM_LABELS.get(
                    rec.program_id.term_system, 'Stage'
                ) if rec.program_id else 'Stage'
                rec.progression_label = f'{label} {rec.progression_no}'
            else:
                rec.progression_label = False

    @api.depends('progression_no', 'program_id.total_terms')
    def _compute_is_final_progression(self):
        for rec in self:
            rec.is_final_progression = (
                rec.progression_no > 0
                and rec.program_id.total_terms > 0
                and rec.progression_no == rec.program_id.total_terms
            )

    @api.depends('curriculum_line_ids')
    def _compute_curriculum_count(self):
        data = self.env['edu.curriculum.line']._read_group(
            domain=[('program_term_id', 'in', self.ids)],
            groupby=['program_term_id'],
            aggregates=['__count'],
        )
        mapped = {pt.id: count for pt, count in data}
        for rec in self:
            rec.curriculum_count = mapped.get(rec.id, 0)

    # ── Python constraints ──────────────────────────────────────────────────────
    @api.constrains('progression_no', 'program_id')
    def _check_progression_no_range(self):
        for rec in self:
            if rec.progression_no <= 0:
                raise ValidationError('Progression number must be positive.')
            if rec.program_id.total_terms and rec.progression_no > rec.program_id.total_terms:
                raise ValidationError(
                    f'Progression number {rec.progression_no} exceeds '
                    f'total terms ({rec.program_id.total_terms}) '
                    f'for program "{rec.program_id.name}".'
                )

    # ── Write / unlink safety ────────────────────────────────────────────────────
    def unlink(self):
        for rec in self:
            if rec.curriculum_count:
                raise UserError(
                    f'Cannot delete program term "{rec.name}" — '
                    f'it has {rec.curriculum_count} curriculum line(s). '
                    'Archive it instead.'
                )
        return super().unlink()

    # ── Smart button ─────────────────────────────────────────────────────────────
    def action_view_curriculum(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Curriculum — {self.name}',
            'res_model': 'edu.curriculum.line',
            'view_mode': 'list,form',
            'domain': [('program_term_id', '=', self.id)],
            'context': {'default_program_term_id': self.id},
        }
