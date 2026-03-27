from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduScheduleTemplate(models.Model):
    """
    Reusable due-date schedule for generating student fee dues.

    Two schedule types:
      - **full**: single due covering 100 % of the amount, due
        immediately (offset_days = 0 on the auto-created line).
      - **installment**: multiple lines, each carrying a percentage
        share and an offset in days from a base date (typically the
        enrollment date or semester start date).

    A schedule template is referenced by ``edu.student.fee.plan.line``
    to control how each plan line's amount is split into individual
    ``edu.student.fee.due`` records.
    """

    _name = 'edu.schedule.template'
    _description = 'Fee Schedule Template'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='E.g. "Full Payment", "3-Installment Plan", "Semester Split".',
    )
    code = fields.Char(
        string='Code',
        help='Optional short reference code.',
    )
    schedule_type = fields.Selection(
        selection=[
            ('full', 'Full Payment'),
            ('installment', 'Installment'),
        ],
        string='Schedule Type',
        required=True,
        default='full',
        help=(
            'Full Payment — single due for the entire amount.\n'
            'Installment — amount split into multiple dues per the '
            'template lines.'
        ),
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    line_ids = fields.One2many(
        comodel_name='edu.schedule.template.line',
        inverse_name='template_id',
        string='Installment Lines',
        copy=True,
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_line_count',
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('schedule_type', 'line_ids')
    def _check_lines(self):
        for rec in self:
            if rec.schedule_type == 'installment' and not rec.line_ids:
                raise ValidationError(
                    f'Installment schedule "{rec.name}" must have at '
                    'least one installment line.'
                )

    @api.constrains('line_ids')
    def _check_percentage_total(self):
        for rec in self:
            if rec.schedule_type != 'installment' or not rec.line_ids:
                continue
            total = sum(rec.line_ids.mapped('percentage'))
            if abs(total - 100.0) > 0.01:
                raise ValidationError(
                    f'Installment percentages for "{rec.name}" must sum '
                    f'to 100 %. Current total: {total:.2f} %.'
                )

    # ── Helper for due generation ─────────────────────────────────────────────
    def get_installments(self):
        """
        Return a list of dicts describing each installment.

        For ``full`` templates, returns a single entry with 100 %
        and 0-day offset.

        Returns:
            list[dict]: [{'installment_no': int, 'percentage': float,
                          'offset_days': int}, ...]
        """
        self.ensure_one()
        if self.schedule_type == 'full':
            return [{'installment_no': 1, 'percentage': 100.0,
                     'offset_days': 0}]
        return [
            {
                'installment_no': line.installment_no,
                'percentage': line.percentage,
                'offset_days': line.offset_days,
            }
            for line in self.line_ids.sorted('installment_no')
        ]


class EduScheduleTemplateLine(models.Model):
    """One installment slot within a schedule template."""

    _name = 'edu.schedule.template.line'
    _description = 'Schedule Template Installment Line'
    _order = 'template_id, installment_no'
    _rec_name = 'display_name'

    template_id = fields.Many2one(
        comodel_name='edu.schedule.template',
        string='Schedule Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    installment_no = fields.Integer(
        string='Installment No.',
        required=True,
        default=1,
        help='Sequential installment number (1, 2, 3 …).',
    )
    percentage = fields.Float(
        string='Percentage (%)',
        required=True,
        default=100.0,
        digits=(5, 2),
        help='Share of the total amount due at this installment.',
    )
    offset_days = fields.Integer(
        string='Offset Days',
        required=True,
        default=0,
        help=(
            'Number of days from the base date (enrollment date or '
            'semester start) when this installment becomes due.'
        ),
    )
    label = fields.Char(
        string='Label',
        help='Optional display label, e.g. "1st Installment".',
    )

    company_id = fields.Many2one(
        related='template_id.company_id',
        string='Company',
        store=True,
    )

    # ── Display name ──────────────────────────────────────────────────────────
    @api.depends('installment_no', 'label', 'percentage')
    def _compute_display_name(self):
        for rec in self:
            lbl = rec.label or f'Installment {rec.installment_no}'
            rec.display_name = f'{lbl} ({rec.percentage:.0f} %)'

    # ── Constraints ───────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_installment',
            'UNIQUE(template_id, installment_no)',
            'Installment number must be unique within a schedule template.',
        ),
    ]

    @api.constrains('percentage')
    def _check_percentage(self):
        for rec in self:
            if rec.percentage <= 0 or rec.percentage > 100:
                raise ValidationError(
                    f'Percentage must be between 0 and 100 — '
                    f'got {rec.percentage} on installment {rec.installment_no}.'
                )

    @api.constrains('offset_days')
    def _check_offset_days(self):
        for rec in self:
            if rec.offset_days < 0:
                raise ValidationError(
                    'Offset days cannot be negative.'
                )
