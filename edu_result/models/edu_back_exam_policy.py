from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduBackExamPolicy(models.Model):
    """
    Reassessment / backlog / back exam behavior policy.

    Governs:
    - Who is eligible for back exams
    - How many attempts are allowed
    - Which marks are carried forward from the original attempt
    - How the replacement / aggregation is performed
    - Whether a grade cap applies after back exam
    """

    _inherit = 'edu.back.exam.policy'
    _description = 'Back Exam Policy'
    _order = 'name'

    name = fields.Char(string='Policy Name', required=True)
    code = fields.Char(string='Code', required=True, copy=False)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
        string='Status', default='draft', required=True,
    )
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )

    applicable_scheme_id = fields.Many2one(
        'edu.assessment.scheme', string='Applicable Scheme',
        help='Leave blank to make this policy universally applicable.',
    )

    # ── Attempt limits ────────────────────────────────────────────────────────
    max_attempts = fields.Integer(
        string='Max Back Exam Attempts', default=2,
        help='Maximum number of back exam attempts allowed per subject.',
    )

    # ── Eligible statuses ─────────────────────────────────────────────────────
    eligible_status_fail = fields.Boolean(
        string='Eligible: Fail', default=True,
    )
    eligible_status_absent = fields.Boolean(
        string='Eligible: Absent', default=True,
    )
    eligible_status_withheld = fields.Boolean(
        string='Eligible: Withheld', default=False,
    )
    eligible_status_incomplete = fields.Boolean(
        string='Eligible: Incomplete', default=True,
    )

    # ── Scope of reattempt ────────────────────────────────────────────────────
    reattempt_scope = fields.Selection(
        selection=[
            ('subject', 'Entire Subject'),
            ('component', 'Specific Component'),
            ('session', 'Specific Exam Session'),
        ],
        string='Reattempt Scope', required=True, default='subject',
    )

    # ── Result replacement ────────────────────────────────────────────────────
    result_replacement_method = fields.Selection(
        selection=[
            ('latest_attempt', 'Use Latest Attempt'),
            ('highest_attempt', 'Use Highest Attempt'),
            ('replace_failed_component_only', 'Replace Failed Component Only'),
            ('average_attempts', 'Average of All Attempts'),
        ],
        string='Result Replacement Method',
        required=True, default='latest_attempt',
    )

    # ── Carry-forward flags ───────────────────────────────────────────────────
    carry_forward_internal_marks = fields.Boolean(
        string='Carry Forward Internal Marks', default=True,
        help='Keep original internal exam marks in recomputation.',
    )
    carry_forward_practical_marks = fields.Boolean(
        string='Carry Forward Practical/Viva Marks', default=True,
    )
    carry_forward_assignment_marks = fields.Boolean(
        string='Carry Forward Assignment Marks', default=True,
    )
    carry_forward_attendance_marks = fields.Boolean(
        string='Carry Forward Attendance Score', default=True,
    )
    carry_forward_class_performance = fields.Boolean(
        string='Carry Forward Class Performance', default=True,
    )

    # ── Grade cap after back exam ─────────────────────────────────────────────
    cap_max_grade_after_back = fields.Char(
        string='Cap Max Grade Letter After Back',
        help='e.g. "B+" — student cannot receive higher than this grade after back exam.',
    )
    cap_max_percentage_after_back = fields.Float(
        string='Cap Max Percentage After Back', default=0.0,
        help='0 means no cap.  e.g. 60 means back exam result is capped at 60%.',
    )
    promotion_after_back_allowed = fields.Boolean(
        string='Promotion Allowed After Clearing Back', default=True,
    )

    # ─────────────────────────────────────────────────────────────────────────

    def get_eligible_statuses(self):
        """Return list of result statuses eligible for back exam."""
        self.ensure_one()
        statuses = []
        if self.eligible_status_fail:
            statuses.append('fail')
        if self.eligible_status_absent:
            statuses.append('absent')
        if self.eligible_status_withheld:
            statuses.append('withheld')
        if self.eligible_status_incomplete:
            statuses.append('incomplete')
        return statuses

    @api.constrains('max_attempts')
    def _check_max_attempts(self):
        for rec in self:
            if rec.max_attempts < 1:
                raise ValidationError('Max back exam attempts must be at least 1.')

    @api.constrains('cap_max_percentage_after_back')
    def _check_cap_percent(self):
        for rec in self:
            if rec.cap_max_percentage_after_back < 0:
                raise ValidationError(
                    'Cap max percentage after back cannot be negative.'
                )
            if rec.cap_max_percentage_after_back > 100:
                raise ValidationError(
                    'Cap max percentage after back cannot exceed 100.'
                )

    def action_activate(self):
        self.write({'state': 'active'})

    _sql_constraints = [
        (
            'unique_code_company',
            'UNIQUE(code, company_id)',
            'Back exam policy code must be unique per company.',
        ),
    ]
