from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduApplicantAcademicHistory(models.Model):
    """
    Structured academic history for an applicant.

    Each record represents one completed qualification level.
    The is_highest_completed flag marks the most recent/relevant entry —
    used by the admission module for eligibility checks.
    """

    _name = 'edu.applicant.academic.history'
    _description = 'Applicant Academic History'
    _order = 'applicant_profile_id, passed_year desc, id'
    _rec_name = 'institution_name'

    applicant_profile_id = fields.Many2one(
        comodel_name='edu.applicant.profile',
        string='Applicant',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Qualification ─────────────────────────────────────────────────────────
    institution_name = fields.Char(string='Institution Name', required=True)
    qualification_level = fields.Selection(
        selection=[
            ('slc_see', 'SLC / SEE'),
            ('plus_two', '+2 / Higher Secondary'),
            ('bachelors', "Bachelor's Degree"),
            ('masters', "Master's Degree"),
            ('mphil', 'M.Phil.'),
            ('phd', 'Ph.D.'),
            ('diploma', 'Diploma / Technical'),
            ('certificate', 'Certificate'),
            ('other', 'Other'),
        ],
        string='Qualification Level',
        required=True,
    )
    board_university = fields.Char(
        string='Board / University',
        help='E.g. NEB, Tribhuvan University, Pokhara University.',
    )
    program_stream = fields.Char(
        string='Program / Stream',
        help='E.g. Science, Management, Arts, Computer Science, BBA.',
    )
    passed_year = fields.Integer(
        string='Passed Year',
        help='Year in which this qualification was completed.',
    )

    # ── Score ─────────────────────────────────────────────────────────────────
    score = fields.Float(
        string='Score / Marks',
        digits=(8, 2),
        default=0.0,
    )
    score_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage (%)'),
            ('gpa', 'GPA'),
            ('cgpa', 'CGPA'),
            ('grade', 'Grade / Division'),
            ('marks', 'Total Marks'),
        ],
        string='Score Type',
    )

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_highest_completed = fields.Boolean(
        string='Highest Completed',
        default=False,
        help=(
            'Mark the most recent highest qualification. '
            'Used by the admission module for eligibility checks.'
        ),
    )
    note = fields.Text(string='Note')

    # ── Python constraints ────────────────────────────────────────────────────
    @api.constrains('passed_year')
    def _check_passed_year(self):
        current_year = date.today().year
        for rec in self:
            if rec.passed_year and (
                rec.passed_year < 1900 or rec.passed_year > current_year + 1
            ):
                raise ValidationError(
                    f'Passed year {rec.passed_year} is not valid. '
                    f'Must be between 1900 and {current_year + 1}.'
                )

    @api.constrains('score', 'score_type')
    def _check_score(self):
        for rec in self:
            if rec.score < 0:
                raise ValidationError(
                    f'Score cannot be negative '
                    f'(institution: "{rec.institution_name}").'
                )
            if rec.score_type == 'percentage' and rec.score > 100:
                raise ValidationError(
                    f'Percentage score cannot exceed 100 '
                    f'(institution: "{rec.institution_name}").'
                )

    @api.constrains('is_highest_completed', 'applicant_profile_id')
    def _check_single_highest(self):
        for rec in self:
            if rec.is_highest_completed:
                others = self.search([
                    ('applicant_profile_id', '=', rec.applicant_profile_id.id),
                    ('is_highest_completed', '=', True),
                    ('id', '!=', rec.id),
                ])
                if others:
                    raise ValidationError(
                        'Only one academic history record per applicant '
                        'can be marked as "Highest Completed".'
                    )
