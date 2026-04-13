from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduAcademicYear(models.Model):
    _name = 'edu.academic.year'
    _description = 'Academic Year'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'
    _rec_name = 'name'

    # ── Identity ────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Academic Year',
        required=True,
        tracking=True,
        help='E.g. 2024-2025',
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Short code, e.g. AY2425',
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        index=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('open', 'Active'),
            ('closed', 'Inactive'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    default_term_type = fields.Selection(
        selection=[
            ('semester', 'Semester (2)'),
            ('trimester', 'Trimester (3)'),
            ('quarter', 'Quarter (4)'),
            ('annual', 'Annual (1)'),
        ],
        string='Term Structure',
        default='semester',
        help='Used when auto-generating terms to split the academic year date range.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ── Children ────────────────────────────────────────────────────────────────
    term_ids = fields.One2many(
        comodel_name='edu.term',
        inverse_name='academic_year_id',
        string='Terms',
    )
    batch_ids = fields.One2many(
        comodel_name='edu.batch',
        inverse_name='academic_year_id',
        string='Batches',
    )

    # ── Counts ──────────────────────────────────────────────────────────────────
    term_count = fields.Integer(
        string='Terms',
        compute='_compute_term_count',
        store=True,
    )
    batch_count = fields.Integer(
        string='Batches',
        compute='_compute_batch_count',
        store=True,
    )

    # ── SQL constraints ─────────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_company_unique', 'UNIQUE(code, company_id)',
         'Academic year code must be unique per company.'),
        ('name_company_unique', 'UNIQUE(name, company_id)',
         'Academic year name must be unique per company.'),
        ('date_check', 'CHECK(date_start < date_end)',
         'End date must be after start date.'),
    ]

    # ── Computed counts (efficient) ───────────────────────────────────────────
    @api.depends('term_ids')
    def _compute_term_count(self):
        data = self.env['edu.term']._read_group(
            [('academic_year_id', 'in', self.ids)],
            ['academic_year_id'],
            ['__count'],
        )
        mapped = {ay.id: count for ay, count in data}
        for rec in self:
            rec.term_count = mapped.get(rec.id, 0)

    @api.depends('batch_ids')
    def _compute_batch_count(self):
        data = self.env['edu.batch']._read_group(
            [('academic_year_id', 'in', self.ids)],
            ['academic_year_id'],
            ['__count'],
        )
        mapped = {ay.id: count for ay, count in data}
        for rec in self:
            rec.batch_count = mapped.get(rec.id, 0)

    # ── Python constraints ──────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start >= rec.date_end:
                raise ValidationError('End date must be after start date.')

    @api.constrains('state', 'company_id')
    def _check_single_open_year(self):
        for rec in self:
            if rec.state == 'open':
                other_open = self.search([
                    ('state', '=', 'open'),
                    ('id', '!=', rec.id),
                    ('company_id', '=', rec.company_id.id),
                ])
                if other_open:
                    raise ValidationError(
                        'Only one academic year can be open at a time. '
                        f'Please close "{other_open[0].name}" first.'
                    )

    @api.constrains('date_start', 'date_end', 'active', 'company_id')
    def _check_no_overlap(self):
        for rec in self:
            if not rec.active:
                continue
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('company_id', '=', rec.company_id.id),
                ('date_start', '<', rec.date_end),
                ('date_end', '>', rec.date_start),
            ])
            if overlapping:
                raise ValidationError(
                    f'Academic year dates overlap with "{overlapping[0].name}".'
                )

    # ── State-based write locking ───────────────────────────────────────────────
    UNLOCKED_FIELDS = frozenset({
        'state', 'active', 'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })

    def write(self, vals):
        if vals.keys() - self.UNLOCKED_FIELDS:
            closed = self.filtered(lambda r: r.state == 'closed')
            if closed:
                raise UserError(
                    'Cannot modify a closed academic year. '
                    f'Reset "{closed[0].name}" to draft first.'
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.term_ids:
                raise UserError(
                    f'Cannot delete academic year "{rec.name}" — '
                    f'it has {len(rec.term_ids)} term(s). Archive it instead.'
                )
            if rec.batch_ids:
                raise UserError(
                    f'Cannot delete academic year "{rec.name}" — '
                    f'it has {len(rec.batch_ids)} batch(es). Archive it instead.'
                )
        return super().unlink()

    # ── State transitions ───────────────────────────────────────────────────────
    def action_open(self):
        for rec in self:
            if not rec.term_ids:
                raise UserError(
                    f'Cannot open "{rec.name}" — add at least one term first.'
                )
        self.write({'state': 'open'})

    def action_close(self):
        for rec in self:
            active_batches = rec.batch_ids.filtered(lambda b: b.state == 'open')
            if active_batches:
                raise UserError(
                    f'Cannot close "{rec.name}" — '
                    f'{len(active_batches)} batch(es) are still active. '
                    'Close them first.'
                )
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    # ── Smart button actions ────────────────────────────────────────────────────
    def action_view_terms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Terms — {self.name}',
            'res_model': 'edu.term',
            'view_mode': 'list,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {'default_academic_year_id': self.id},
        }

    def action_view_batches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Batches — {self.name}',
            'res_model': 'edu.batch',
            'view_mode': 'list,form',
            'domain': [('academic_year_id', '=', self.id)],
            'context': {'default_academic_year_id': self.id},
        }

    # ── Generate terms ──────────────────────────────────────────────────────────
    def action_generate_terms(self):
        """
        Auto-create academic terms by evenly splitting the year's date range
        according to default_term_type (semester=2, trimester=3, quarter=4, annual=1).
        Skips terms whose sequence already exists. Never deletes existing terms.
        """
        self.ensure_one()
        if not self.date_start or not self.date_end:
            raise UserError('Set start and end dates before generating terms.')
        if not self.default_term_type:
            raise UserError('Set a Term Structure before generating terms.')

        count_map = {'semester': 2, 'trimester': 3, 'quarter': 4, 'annual': 1}
        label_map = {'semester': 'Semester', 'trimester': 'Trimester',
                     'quarter': 'Quarter', 'annual': 'Year'}
        n = count_map[self.default_term_type]
        label = label_map[self.default_term_type]
        year_code = (self.code or self.name or '')[:6].replace(' ', '')

        total_days = (self.date_end - self.date_start).days
        chunk = total_days // n

        existing_seqs = set(self.term_ids.mapped('sequence'))
        to_create = []
        for i in range(n):
            seq = (i + 1) * 10
            if seq in existing_seqs:
                continue
            t_start = self.date_start + timedelta(days=i * chunk)
            t_end = (self.date_start + timedelta(days=(i + 1) * chunk - 1)
                     if i < n - 1 else self.date_end)
            code_candidate = f'{label[:3].upper()}{i + 1}-{year_code}'
            # ensure code uniqueness by appending id suffix if needed
            to_create.append({
                'name': f'{label} {i + 1}',
                'code': code_candidate,
                'academic_year_id': self.id,
                'term_type': self.default_term_type,
                'sequence': seq,
                'date_start': t_start,
                'date_end': t_end,
            })

        if not to_create:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Nothing to Generate',
                    'message': 'All terms already exist for this academic year.',
                    'type': 'info',
                    'sticky': False,
                },
            }

        self.env['edu.term'].create(to_create)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Terms Generated',
                'message': f'Created {len(to_create)} {label.lower()}(s) for "{self.name}".',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ── Helper: get current open year ───────────────────────────────────────────
    @api.model
    def _get_current_year(self, company_id=None):
        """Return the currently open academic year for the given company."""
        company_id = company_id or self.env.company.id
        return self.search([
            ('state', '=', 'open'),
            ('company_id', '=', company_id),
        ], limit=1)
