from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduGradingScheme(models.Model):
    """
    Grade conversion table.

    Maps percentage ranges to grade letters, grade points, and remarks.
    Supports both percentage-only and GPA-based systems.
    """

    _name = 'edu.grading.scheme'
    _description = 'Grading Scheme'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Scheme Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, copy=False)
    active = fields.Boolean(default=True, tracking=True)
    result_system = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('gpa', 'GPA'),
            ('both', 'Percentage + GPA'),
        ],
        string='Result System', required=True, default='percentage',
    )
    use_letters = fields.Boolean(
        string='Use Grade Letters', default=True,
        help='e.g. A+, A, B+, B, C, D, F',
    )
    use_grade_points = fields.Boolean(
        string='Use Grade Points', default=False,
        help='e.g. 4.0, 3.7, 3.3 …',
    )
    rounding_method = fields.Selection(
        selection=[
            ('round', 'Round (nearest)'),
            ('floor', 'Floor (round down)'),
            ('ceil', 'Ceil (round up)'),
        ],
        string='Rounding Method', default='round',
    )
    rounding_precision = fields.Integer(
        string='Decimal Places', default=2,
    )
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    line_ids = fields.One2many(
        'edu.grading.scheme.line', 'grading_scheme_id',
        string='Grade Bands', copy=True,
    )

    @api.constrains('rounding_precision')
    def _check_precision(self):
        for rec in self:
            if rec.rounding_precision < 0:
                raise ValidationError('Decimal places cannot be negative.')

    def get_grade(self, percentage):
        """Return (grade_letter, grade_point, remark, is_fail) for a given percentage."""
        self.ensure_one()
        for band in self.line_ids.sorted('sequence'):
            if band.min_percent <= percentage <= band.max_percent:
                return (
                    band.grade_letter,
                    band.grade_point,
                    band.result_remark or '',
                    band.is_fail,
                )
        return ('', 0.0, '', True)

    _sql_constraints = [
        (
            'unique_code_company',
            'UNIQUE(code, company_id)',
            'Grading scheme code must be unique per company.',
        ),
    ]


class EduGradingSchemeLine(models.Model):
    """One grade band within a grading scheme."""

    _name = 'edu.grading.scheme.line'
    _description = 'Grading Scheme Line'
    _order = 'grading_scheme_id, sequence desc'

    grading_scheme_id = fields.Many2one(
        'edu.grading.scheme', string='Grading Scheme',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)

    min_percent = fields.Float(
        string='Min %', required=True, digits=(6, 2),
    )
    max_percent = fields.Float(
        string='Max %', required=True, digits=(6, 2),
    )
    grade_letter = fields.Char(string='Grade Letter', size=8)
    grade_point = fields.Float(
        string='Grade Point', digits=(4, 2), default=0.0,
    )
    result_remark = fields.Char(
        string='Remark', help='e.g. Outstanding, Distinction, Pass, Fail',
    )
    is_fail = fields.Boolean(
        string='Fail Band', default=False,
        help='Students in this band are considered failed.',
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('min_percent', 'max_percent')
    def _check_range(self):
        for rec in self:
            if rec.min_percent < 0 or rec.max_percent > 100:
                raise ValidationError(
                    'Grade band percentages must be between 0 and 100.'
                )
            if rec.min_percent > rec.max_percent:
                raise ValidationError(
                    f'Min % ({rec.min_percent}) cannot exceed Max % ({rec.max_percent}).'
                )

    @api.constrains('min_percent', 'max_percent', 'grading_scheme_id')
    def _check_no_overlap(self):
        for rec in self:
            siblings = rec.grading_scheme_id.line_ids.filtered(
                lambda l: l.id != rec.id
            )
            for sib in siblings:
                if rec.min_percent <= sib.max_percent and rec.max_percent >= sib.min_percent:
                    raise ValidationError(
                        f'Grade band {rec.min_percent}–{rec.max_percent} '
                        f'overlaps with band {sib.min_percent}–{sib.max_percent}.'
                    )

    @api.constrains('grade_point')
    def _check_grade_point(self):
        for rec in self:
            if rec.grade_point < 0:
                raise ValidationError('Grade point cannot be negative.')
