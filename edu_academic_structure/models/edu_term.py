from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduTerm(models.Model):
    _name = 'edu.term'
    _description = 'Academic Term (flexible: semester, trimester, quarter, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id, sequence'
    _rec_name = 'name'

    name = fields.Char(
        string='Term Name',
        required=True,
        tracking=True,
        help='E.g. Semester 1, Term 2, Quarter 3',
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Short code, e.g. SEM1-2425, T2-2425',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    term_type = fields.Selection(
        selection=[
            ('semester', 'Semester'),
            ('trimester', 'Trimester'),
            ('quarter', 'Quarter'),
            ('annual', 'Annual'),
            ('custom', 'Custom'),
        ],
        string='Term Type',
        default='semester',
        required=True,
        tracking=True,
        help='Describes the academic calendar structure.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        required=True,
        help='Order of the term within the academic year.',
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        related='academic_year_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── SQL constraints ─────────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Term code must be unique.'),
        (
            'name_year_unique',
            'UNIQUE(academic_year_id, name)',
            'Term name must be unique within an academic year.',
        ),
        ('date_check', 'CHECK(date_start < date_end)',
         'Term end date must be after start date.'),
        ('sequence_positive', 'CHECK(sequence > 0)',
         'Sequence must be a positive number.'),
    ]

    # ── Python constraints ──────────────────────────────────────────────────────
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start >= rec.date_end:
                raise ValidationError('Term end date must be after start date.')

    @api.constrains('date_start', 'date_end', 'academic_year_id')
    def _check_within_academic_year(self):
        for rec in self:
            ay = rec.academic_year_id
            if not (ay.date_start and ay.date_end):
                continue
            if rec.date_start and rec.date_start < ay.date_start:
                raise ValidationError(
                    f'Term start date cannot be before academic year start date ({ay.date_start}).'
                )
            if rec.date_end and rec.date_end > ay.date_end:
                raise ValidationError(
                    f'Term end date cannot exceed academic year end date ({ay.date_end}).'
                )

    @api.constrains('date_start', 'date_end', 'academic_year_id')
    def _check_no_term_overlap(self):
        for rec in self:
            overlapping = self.search([
                ('id', '!=', rec.id),
                ('academic_year_id', '=', rec.academic_year_id.id),
                ('date_start', '<', rec.date_end),
                ('date_end', '>', rec.date_start),
            ])
            if overlapping:
                raise ValidationError(
                    f'Term dates overlap with "{overlapping[0].name}" in the same academic year.'
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
                if rec.academic_year_id.state == 'closed':
                    raise UserError(
                        f'Cannot modify term "{rec.name}" — '
                        f'academic year "{rec.academic_year_id.name}" is closed.'
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.academic_year_id.state != 'draft':
                raise UserError(
                    f'Cannot delete term "{rec.name}" — '
                    f'academic year "{rec.academic_year_id.name}" is not in draft. '
                    'Archive it instead.'
                )
        return super().unlink()
