from odoo import api, fields, models
from odoo.exceptions import UserError


class EduResultSubjectLine(models.Model):
    """
    Final subject-level computed result for one student.

    Stores a full snapshot of the academic context at computation time so that
    the record remains historically correct even after batch promotions.

    Component breakdown is stored in child edu.result.subject.component records.
    """

    _name = 'edu.result.subject.line'
    _description = 'Result Subject Line'
    _order = 'result_session_id, student_id, subject_id'
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
    subject_id = fields.Many2one(
        'edu.subject', string='Subject', ondelete='restrict', index=True,
    )
    curriculum_line_id = fields.Many2one(
        'edu.curriculum.line', string='Curriculum Line', ondelete='restrict', index=True,
    )

    # ── Computed marks ────────────────────────────────────────────────────────
    component_total = fields.Float(
        string='Component Total', digits=(10, 4),
        help='Sum of all normalized component marks before weightage.',
    )
    weighted_total = fields.Float(
        string='Weighted Total', digits=(10, 4),
        help='Sum of all weighted contributions (i.e. the final weighted percentage).',
    )
    percentage = fields.Float(
        string='Percentage', digits=(6, 2),
    )

    # ── Grade ─────────────────────────────────────────────────────────────────
    grade_letter = fields.Char(string='Grade', size=8)
    grade_point = fields.Float(string='Grade Point', digits=(4, 2))

    # ── Pass / fail status ────────────────────────────────────────────────────
    is_pass = fields.Boolean(string='Pass', index=True)
    is_failed = fields.Boolean(string='Failed', index=True)
    backlog_flag = fields.Boolean(string='Backlog', index=True)

    # ── Special conditions ────────────────────────────────────────────────────
    is_absent = fields.Boolean(string='Absent')
    is_withheld = fields.Boolean(string='Withheld')
    is_malpractice = fields.Boolean(string='Malpractice')
    is_exempt = fields.Boolean(string='Exempt')

    # ── Backlog / back exam ───────────────────────────────────────────────────
    is_backlog_subject = fields.Boolean(string='Backlog Subject', index=True)
    is_back_exam_eligible = fields.Boolean(string='Back Exam Eligible')
    attempt_count = fields.Integer(string='Attempts', default=1)
    effective_attempt_no = fields.Integer(string='Effective Attempt No.', default=1)
    has_back_exam = fields.Boolean(string='Back Exam Taken')
    back_exam_cleared = fields.Boolean(string='Back Exam Cleared')

    # ── History chain ─────────────────────────────────────────────────────────
    original_result_status = fields.Char(
        string='Original Status',
        help='Status as computed in the initial run.',
    )
    current_result_status = fields.Char(
        string='Current Status',
        help='Status after any back exam recomputation.',
    )
    recomputed_after_back = fields.Boolean(
        string='Recomputed After Back Exam',
    )
    superseded_by_result_subject_line_id = fields.Many2one(
        'edu.result.subject.line',
        string='Superseded By',
        ondelete='set null',
        help='When a back exam recomputation creates a new line, the old line '
             'is linked here so history is preserved.',
    )

    remarks = fields.Char(string='Remarks')

    # ── Component breakdown ───────────────────────────────────────────────────
    component_ids = fields.One2many(
        'edu.result.subject.component', 'result_subject_line_id',
        string='Component Breakdown',
    )
    component_count = fields.Integer(
        string='Components', compute='_compute_component_count',
    )

    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('student_id', 'subject_id', 'result_session_id')
    def _compute_display_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            subject = rec.subject_id.name or ''
            session = rec.result_session_id.name or ''
            rec.display_name = f'{student} | {subject} | {session}'

    @api.depends('component_ids')
    def _compute_component_count(self):
        for rec in self:
            rec.component_count = len(rec.component_ids)

    def write(self, vals):
        """Block edits on published/closed sessions."""
        for rec in self:
            session_state = rec.result_session_id.state
            if session_state in ('published', 'closed'):
                allowed = {
                    'remarks',
                    'is_back_exam_eligible',
                    'has_back_exam',
                    'back_exam_cleared',
                    'superseded_by_result_subject_line_id',
                }
                disallowed = set(vals.keys()) - allowed
                if disallowed:
                    raise UserError(
                        f'Cannot modify {", ".join(disallowed)} on a '
                        f'{session_state} result session.'
                    )
        return super().write(vals)


class EduResultSubjectComponent(models.Model):
    """
    Per-scheme-line contribution record for a result subject line.

    Stores the raw, normalized, and weighted marks for each assessment scheme
    line, giving full auditability of how the final percentage was reached.
    """

    _name = 'edu.result.subject.component'
    _description = 'Result Subject Component'
    _order = 'result_subject_line_id, sequence'

    result_subject_line_id = fields.Many2one(
        'edu.result.subject.line', string='Subject Result Line',
        required=True, ondelete='cascade', index=True,
    )
    scheme_line_id = fields.Many2one(
        'edu.assessment.scheme.line', string='Scheme Line',
        ondelete='set null',
    )
    name = fields.Char(string='Component Name', required=True)
    sequence = fields.Integer(
        related='scheme_line_id.sequence', store=True,
    )

    # ── Marks ─────────────────────────────────────────────────────────────────
    raw_obtained = fields.Float(
        string='Raw Obtained', digits=(10, 4),
        help='Aggregated raw marks from source records.',
    )
    raw_max = fields.Float(
        string='Raw Max', digits=(10, 4),
        help='Total possible raw marks from source records.',
    )
    normalized_obtained = fields.Float(
        string='Normalized Obtained', digits=(10, 4),
        help='Obtained marks scaled to the scheme line max_marks.',
    )
    normalized_max = fields.Float(
        string='Normalized Max', digits=(10, 4),
    )
    weighted_contribution = fields.Float(
        string='Weighted Contribution', digits=(10, 4),
        help='Contribution to the overall percentage after applying weightage_percent.',
    )
    weightage_percent = fields.Float(
        string='Weightage %', digits=(6, 2),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_pass = fields.Boolean(string='Component Pass')
    is_mandatory = fields.Boolean(string='Mandatory')
    records_count = fields.Integer(
        string='Source Records',
        help='Number of source records used in aggregation.',
    )
    notes = fields.Char(string='Notes')
