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
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
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
            active_batches = rec.batch_ids.filtered(lambda b: b.state == 'active')
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

    # ── Helper: get current open year ───────────────────────────────────────────
    @api.model
    def _get_current_year(self, company_id=None):
        """Return the currently open academic year for the given company."""
        company_id = company_id or self.env.company.id
        return self.search([
            ('state', '=', 'open'),
            ('company_id', '=', company_id),
        ], limit=1)
