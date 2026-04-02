from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import re


class EduBatch(models.Model):
    _name = 'edu.batch'
    _description = 'Program Batch / Intake Cohort'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_id'
    _rec_name = 'name'

    # ── Computed / auto-generated identity ────────────────────────────────────
    name = fields.Char(
        string='Batch Name',
        compute='_compute_name_code',
        store=True,
        tracking=True,
    )
    code = fields.Char(
        string='Batch Code',
        compute='_compute_name_code',
        store=True,
        tracking=True,
    )

    # ── Core relations ─────────────────────────────────────────────────────────
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        default=lambda self: self.env['edu.academic.year']._get_current_year(),
    )

    # ── Progression tracking ─────────────────────────────────────────────────
    current_program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Current Semester',
        ondelete='restrict',
        tracking=True,
        domain="[('program_id', '=', program_id)]",
        help='The Semester stage this batch is currently in '
             '(e.g. Semester 3 of BCS).',
    )

    # ── Optional intake differentiation ───────────────────────────────────────
    intake_name = fields.Char(
        string='Intake',
        tracking=True,
        help='Optional intake label, e.g. Spring, Fall, Jan, Sep. '
             'Leave blank if only one batch per year.',
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    start_date = fields.Date(string='Start Date', tracking=True)
    end_date = fields.Date(string='End Date', tracking=True)

    # ── Capacity & state ──────────────────────────────────────────────────────
    capacity = fields.Integer(
        string='Total Capacity',
        default=0,
        help='Maximum students in this batch (0 = unlimited).',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        related='academic_year_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Children ────────────────────────────────────────────────────────────────
    section_ids = fields.One2many(
        comodel_name='edu.section',
        inverse_name='batch_id',
        string='Sections',
    )
    section_count = fields.Integer(
        string='Sections',
        compute='_compute_section_count',
        store=True,
    )

    # ── SQL constraints ────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'batch_unique',
            'UNIQUE(program_id, academic_year_id, intake_name)',
            'A batch already exists for this program, academic year, and intake.',
        ),
    ]

    # ── Compute: name and code ─────────────────────────────────────────────────
    @api.depends('program_id', 'program_id.code', 'academic_year_id',
                 'academic_year_id.name', 'intake_name')
    def _compute_name_code(self):
        for rec in self:
            prog_code = (rec.program_id.code or '').strip().upper()
            ay_name = (rec.academic_year_id.name or '').strip()
            intake = (rec.intake_name or '').strip()

            if prog_code and ay_name:
                if intake:
                    rec.name = f'{prog_code} - {ay_name} - {intake}'
                    clean_ay = re.sub(r'[^A-Z0-9]', '', ay_name.upper())[:8]
                    clean_intake = re.sub(r'[^A-Z0-9]', '', intake.upper())[:6]
                    rec.code = f'{prog_code}-{clean_ay}-{clean_intake}'
                else:
                    rec.name = f'{prog_code} - {ay_name}'
                    clean_ay = re.sub(r'[^A-Z0-9]', '', ay_name.upper())[:8]
                    rec.code = f'{prog_code}-{clean_ay}'
            else:
                rec.name = False
                rec.code = False

    # ── Compute: section count ─────────────────────────────────────────────────
    @api.depends('section_ids')
    def _compute_section_count(self):
        data = self.env['edu.section']._read_group(
            [('batch_id', 'in', self.ids)],
            ['batch_id'],
            ['__count'],
        )
        mapped = {batch.id: count for batch, count in data}
        for rec in self:
            rec.section_count = mapped.get(rec.id, 0)

    # ── Compute: display name ──────────────────────────────────────────────────
    @api.depends('name', 'state')
    def _compute_display_name(self):
        state_label = dict(self._fields['state'].selection)
        for rec in self:
            status = state_label.get(rec.state, '')
            rec.display_name = f'{rec.name or ""} [{status}]' if rec.name else status

    # ── Python constraints ─────────────────────────────────────────────────────
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date >= rec.end_date:
                raise ValidationError('Batch end date must be after start date.')

    @api.constrains('capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 0:
                raise ValidationError('Capacity cannot be negative.')

    @api.constrains('capacity', 'section_ids')
    def _check_batch_capacity_vs_sections(self):
        for rec in self:
            if rec.capacity == 0:
                continue
            total = sum(rec.section_ids.mapped('capacity'))
            if total > rec.capacity:
                raise ValidationError(
                    f'Batch capacity ({rec.capacity}) is less than the combined '
                    f'section capacity ({total}) for batch "{rec.name}". '
                    'Increase the batch capacity or reduce section capacities.'
                )

    @api.constrains('current_program_term_id', 'program_id')
    def _check_program_term_belongs_to_program(self):
        for rec in self:
            if (
                rec.current_program_term_id
                and rec.current_program_term_id.program_id != rec.program_id
            ):
                raise ValidationError(
                    f'Current progression "{rec.current_program_term_id.name}" '
                    f'does not belong to program "{rec.program_id.name}".'
                )

    @api.constrains('program_id', 'academic_year_id', 'intake_name')
    def _check_batch_unique_no_intake(self):
        """
        Supplement the SQL UNIQUE constraint: PostgreSQL does not treat two NULLs
        as equal in a UNIQUE index, so we enforce uniqueness for blank intake names
        in Python.
        """
        for rec in self:
            if rec.intake_name:
                continue  # SQL unique constraint already covers non-null intake
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('program_id', '=', rec.program_id.id),
                ('academic_year_id', '=', rec.academic_year_id.id),
                ('intake_name', 'in', [False, '']),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'A batch without an intake label already exists for program '
                    f'"{rec.program_id.name}" in "{rec.academic_year_id.name}". '
                    'Use an intake name to differentiate multiple batches.'
                )

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('program_id')
    def _onchange_program_id(self):
        """Clear current_program_term if it doesn't match the new program."""
        if (
            self.current_program_term_id
            and self.current_program_term_id.program_id != self.program_id
        ):
            self.current_program_term_id = False

    # ── State-based write locking ───────────────────────────────────────────────
    UNLOCKED_FIELDS = frozenset({
        'state', 'active', 'current_program_term_id',
        'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })
    IDENTITY_FIELDS = frozenset({
        'program_id', 'academic_year_id', 'intake_name',
    })

    def write(self, vals):
        changing_fields = vals.keys()
        # Closed: block all except unlocked
        if changing_fields - self.UNLOCKED_FIELDS:
            closed = self.filtered(lambda r: r.state == 'closed')
            if closed:
                raise UserError(
                    'Cannot modify a closed batch. '
                    f'Reset "{closed[0].name}" to draft first.'
                )
        # Active: block identity changes
        if changing_fields & self.IDENTITY_FIELDS:
            active_recs = self.filtered(lambda r: r.state == 'active')
            if active_recs:
                raise UserError(
                    'Cannot change program, academic year, or intake '
                    f'on active batch "{active_recs[0].name}". '
                    'Close or reset to draft first.'
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.section_ids:
                raise UserError(
                    f'Cannot delete batch "{rec.name}" — '
                    f'it has {len(rec.section_ids)} section(s). Archive it instead.'
                )
            if rec.state != 'draft':
                raise UserError(
                    f'Cannot delete batch "{rec.name}" — '
                    'only draft batches can be deleted. Archive it instead.'
                )
        return super().unlink()

    # ── State transitions ──────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('current_program_term_id') and vals.get('program_id'):
                first_term = self.env['edu.program.term'].search(
                    [
                        ('program_id', '=', vals['program_id']),
                        ('progression_no', '=', 1),
                    ],
                    limit=1,
                )
                if first_term:
                    vals['current_program_term_id'] = first_term.id
        batches = super().create(vals_list)
        for batch in batches:
            self.env['edu.section'].create({
                'batch_id': batch.id,
                'name': 'A',
                'code': 'SEC-A',
                'capacity': 0,
            })
        return batches

    def action_activate(self):
        for rec in self:
            if rec.academic_year_id.state != 'open':
                raise UserError(
                    f'Cannot activate batch "{rec.name}" — '
                    f'academic year "{rec.academic_year_id.name}" is not open.'
                )
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_sections(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sections — {self.name}',
            'res_model': 'edu.section',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
        }
