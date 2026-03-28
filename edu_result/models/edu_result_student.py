from odoo import api, fields, models
from odoo.exceptions import UserError


class EduResultStudent(models.Model):
    """
    Final student-level aggregated result row.

    Aggregates subject-level outcomes into a single, reportable, student result
    for a result session.  This is the record used for promotion decisions,
    transcript generation, and parent/student publication.
    """

    _name = 'edu.result.student'
    _description = 'Student Result'
    _order = 'result_session_id, batch_id, section_id, student_id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name', store=True,
    )

    # ── Session ───────────────────────────────────────────────────────────────
    result_session_id = fields.Many2one(
        'edu.result.session', string='Result Session',
        required=True, ondelete='cascade', index=True,
    )

    # ── Student snapshot ──────────────────────────────────────────────────────
    student_id = fields.Many2one(
        'edu.student', string='Student',
        required=True, ondelete='restrict', index=True,
    )
    enrollment_id = fields.Many2one(
        'edu.enrollment', string='Enrollment',
        ondelete='restrict', index=True,
    )
    student_progression_history_id = fields.Many2one(
        'edu.student.progression.history',
        string='Progression History',
        required=True, ondelete='restrict', index=True,
    )

    # ── Academic context snapshot ─────────────────────────────────────────────
    batch_id = fields.Many2one(
        'edu.batch', string='Batch', ondelete='restrict', index=True,
    )
    section_id = fields.Many2one(
        'edu.section', string='Section', ondelete='restrict',
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Program Term', ondelete='restrict', index=True,
    )

    # ── Aggregated marks ──────────────────────────────────────────────────────
    total_marks = fields.Float(
        string='Total Marks', digits=(10, 2),
        help='Total possible marks across all subjects.',
    )
    obtained_marks = fields.Float(
        string='Obtained Marks', digits=(10, 2),
    )
    percentage = fields.Float(
        string='Percentage', digits=(6, 2),
    )
    gpa = fields.Float(
        string='GPA', digits=(4, 2),
    )
    grade_letter = fields.Char(string='Grade', size=8)

    # ── Result status ─────────────────────────────────────────────────────────
    result_status = fields.Selection(
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('promoted', 'Promoted'),
            ('promoted_with_backlog', 'Promoted with Backlog'),
            ('repeat', 'Repeat'),
            ('withheld', 'Result Withheld'),
            ('incomplete', 'Incomplete'),
            ('malpractice', 'Malpractice'),
        ],
        string='Result Status', required=True, default='incomplete',
        index=True,
    )

    # ── Backlog tracking ──────────────────────────────────────────────────────
    backlog_count = fields.Integer(string='Total Backlogs', default=0)
    cleared_backlog_count = fields.Integer(
        string='Cleared Backlogs', default=0,
    )
    remaining_backlog_count = fields.Integer(
        string='Remaining Backlogs',
        compute='_compute_remaining_backlogs', store=True,
    )
    has_active_backlog = fields.Boolean(
        string='Has Active Backlog', index=True,
    )

    # ── Promotion ─────────────────────────────────────────────────────────────
    promotion_hold_reason = fields.Char(
        string='Promotion Hold Reason',
        help='Reason if student cannot be promoted.',
    )
    distinction_flag = fields.Boolean(string='Distinction')

    remarks = fields.Text(string='Remarks')
    published_on = fields.Datetime(string='Published On', readonly=True)

    # ── Subject lines (for quick navigation) ──────────────────────────────────
    subject_line_ids = fields.One2many(
        'edu.result.subject.line', 'student_progression_history_id',
        string='Subject Results',
        domain="[('result_session_id', '=', result_session_id)]",
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('student_id', 'result_session_id')
    def _compute_display_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            session = rec.result_session_id.name or ''
            rec.display_name = f'{student} | {session}'

    @api.depends('backlog_count', 'cleared_backlog_count')
    def _compute_remaining_backlogs(self):
        for rec in self:
            rec.remaining_backlog_count = max(
                0, rec.backlog_count - rec.cleared_backlog_count
            )

    def write(self, vals):
        """Block edits on published/closed sessions."""
        for rec in self:
            session_state = rec.result_session_id.state
            if session_state in ('published', 'closed'):
                allowed = {
                    'remarks',
                    'promotion_hold_reason',
                    'published_on',
                    'cleared_backlog_count',
                    'remaining_backlog_count',
                    'has_active_backlog',
                    'result_status',
                }
                disallowed = set(vals.keys()) - allowed
                if disallowed:
                    raise UserError(
                        f'Cannot modify {", ".join(disallowed)} on a '
                        f'{session_state} result session.'
                    )
        return super().write(vals)

    def action_view_subject_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Subject Results — {self.student_id.display_name}',
            'res_model': 'edu.result.subject.line',
            'view_mode': 'list,form',
            'domain': [
                ('result_session_id', '=', self.result_session_id.id),
                ('student_progression_history_id', '=', self.student_progression_history_id.id),
            ],
        }
