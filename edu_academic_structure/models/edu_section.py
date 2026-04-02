from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduSection(models.Model):
    _name = 'edu.section'
    _description = 'Batch Section'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'batch_id, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Section Name',
        required=True,
        tracking=True,
        help='E.g. A, B, Morning, Evening',
    )
    code = fields.Char(
        string='Section Code',
        required=True,
        tracking=True,
        help='Short code, e.g. SEC-A, SEC-B',
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    capacity = fields.Integer(
        string='Capacity',
        default=0,
        help='Maximum students in this section (0 = unlimited).',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='batch_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Convenience: full label ────────────────────────────────────────────────
    full_label = fields.Char(
        string='Full Label',
        compute='_compute_full_label',
        store=True,
        help='Batch name + section name for quick reference.',
    )

    # ── SQL constraints ────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'name_batch_unique',
            'UNIQUE(batch_id, name)',
            'Section name must be unique within a batch.',
        ),
        (
            'code_batch_unique',
            'UNIQUE(batch_id, code)',
            'Section code must be unique within a batch.',
        ),
    ]

    # ── Computed ───────────────────────────────────────────────────────────────
    @api.depends('batch_id', 'batch_id.name', 'name')
    def _compute_full_label(self):
        for rec in self:
            batch_name = rec.batch_id.name or ''
            rec.full_label = f'{batch_name} / {rec.name}' if batch_name else rec.name

    # ── Constraints ────────────────────────────────────────────────────────────
    @api.constrains('capacity')
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 0:
                raise ValidationError('Section capacity cannot be negative.')

    @api.constrains('capacity', 'batch_id')
    def _check_section_capacity_vs_batch(self):
        for rec in self:
            batch = rec.batch_id
            if not batch or batch.capacity == 0:
                continue
            total = sum(batch.section_ids.mapped('capacity'))
            if total > batch.capacity:
                raise ValidationError(
                    f'Total section capacity ({total}) exceeds the batch '
                    f'capacity ({batch.capacity}) for batch "{batch.name}". '
                    'Please reduce the section capacity or increase the batch capacity.'
                )

    # ── State-based locking via parent ──────────────────────────────────────────
    UNLOCKED_FIELDS = frozenset({
        'active', 'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })

    def write(self, vals):
        if vals.keys() - self.UNLOCKED_FIELDS:
            for rec in self:
                if rec.batch_id.state == 'closed':
                    raise UserError(
                        f'Cannot modify section "{rec.name}" — '
                        f'batch "{rec.batch_id.name}" is closed.'
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.batch_id.state != 'draft':
                raise UserError(
                    f'Cannot delete section "{rec.name}" — '
                    f'batch "{rec.batch_id.name}" is not in draft. '
                    'Archive it instead.'
                )
        return super().unlink()
