import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .edu_assessment_scheme import ATTEMPT_TYPE_SELECTION

_logger = logging.getLogger(__name__)

STATUS_SELECTION = [
    ('present', 'Present'),
    ('absent', 'Absent'),
    ('exempt', 'Exempt'),
    ('withheld', 'Withheld'),
    ('malpractice', 'Malpractice'),
]


class EduExamMarksheet(models.Model):
    """Exam Marksheet — raw marks capture for one student in one exam paper.

    Snapshot fields (batch, section, program_term, etc.) are stored directly
    — never as related fields — so historical records remain correct even if
    student placements change later.

    The is_locked flag and paper state gate prevent edits after results are
    finalised.  Admins can unlock individual marksheets when corrections are
    needed.

    Attempt tracking: each back/makeup/improvement attempt creates a new
    marksheet linked to the previous one via previous_marksheet_id.  Only
    the latest attempt has is_latest_attempt=True.
    """

    _name = 'edu.exam.marksheet'
    _description = 'Exam Marksheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_paper_id, student_id, attempt_no'
    _rec_name = 'display_name'

    # ── Computed display name ─────────────────────────────────────────────────

    display_name = fields.Char(
        string='Marksheet',
        compute='_compute_display_name',
        store=True,
    )

    # ── Paper / session links ─────────────────────────────────────────────────

    exam_paper_id = fields.Many2one(
        comodel_name='edu.exam.paper',
        string='Exam Paper',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Exam Session',
        related='exam_paper_id.exam_session_id',
        store=True,
        index=True,
    )
    exam_session_state = fields.Selection(
        related='exam_paper_id.exam_session_id.state',
        string='Session State',
        store=True,
    )
    exam_paper_state = fields.Selection(
        related='exam_paper_id.state',
        string='Paper State',
        store=True,
    )

    # ── Student ───────────────────────────────────────────────────────────────

    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )

    # ── Snapshot fields (stored, not related) ─────────────────────────────────

    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        ondelete='set null',
        index=True,
    )
    student_progression_history_id = fields.Many2one(
        comodel_name='edu.student.progression.history',
        string='Progression History',
        ondelete='restrict',
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        ondelete='restrict',
        index=True,
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        ondelete='restrict',
        index=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        ondelete='restrict',
        index=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        ondelete='restrict',
        index=True,
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='edu.curriculum.line',
        string='Curriculum Line',
        ondelete='restrict',
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        ondelete='restrict',
        index=True,
    )

    # ── Marks ─────────────────────────────────────────────────────────────────

    status = fields.Selection(
        selection=STATUS_SELECTION,
        string='Status',
        required=True,
        default='present',
        tracking=True,
        index=True,
    )
    raw_marks = fields.Float(
        string='Raw Marks',
        default=0.0,
        tracking=True,
    )
    grace_marks = fields.Float(
        string='Grace Marks',
        default=0.0,
        tracking=True,
    )
    final_marks = fields.Float(
        string='Final Marks',
        compute='_compute_final_marks',
        store=True,
        tracking=True,
    )
    max_marks = fields.Float(
        string='Max Marks',
        related='exam_paper_id.max_marks',
        store=True,
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        related='exam_paper_id.pass_marks',
        store=True,
    )
    is_pass = fields.Boolean(
        string='Pass',
        compute='_compute_is_pass',
        store=True,
    )

    # ── Attendance ────────────────────────────────────────────────────────────

    attendance_percent_snapshot = fields.Float(
        string='Attendance %',
        default=0.0,
        help='Attendance percentage at the time of exam; snapshotted from attendance register.',
    )
    attendance_eligible = fields.Boolean(
        string='Attendance Eligible',
        default=True,
        help='Whether the student meets the attendance requirement for this exam.',
    )

    # ── Audit ─────────────────────────────────────────────────────────────────

    entered_by = fields.Many2one(
        comodel_name='res.users',
        string='Entered By',
        default=lambda self: self.env.user,
        index=True,
    )
    entered_on = fields.Datetime(
        string='Entered On',
        default=fields.Datetime.now,
    )
    verified_by = fields.Many2one(
        comodel_name='res.users',
        string='Verified By',
        tracking=True,
    )
    verified_on = fields.Datetime(
        string='Verified On',
        tracking=True,
    )
    is_locked = fields.Boolean(
        string='Locked',
        default=False,
        tracking=True,
        help='When locked, marks cannot be edited unless unlocked by an admin.',
    )

    # ── Attempt tracking ──────────────────────────────────────────────────────

    attempt_no = fields.Integer(
        string='Attempt No.',
        default=1,
        tracking=True,
    )
    attempt_type = fields.Selection(
        selection=ATTEMPT_TYPE_SELECTION,
        string='Attempt Type',
        required=True,
        default='regular',
        tracking=True,
        index=True,
    )
    previous_marksheet_id = fields.Many2one(
        comodel_name='edu.exam.marksheet',
        string='Previous Attempt',
        ondelete='set null',
    )
    is_latest_attempt = fields.Boolean(
        string='Latest Attempt',
        default=True,
        index=True,
    )
    is_back_attempt = fields.Boolean(
        string='Back Attempt',
        compute='_compute_is_back_attempt',
        store=True,
    )
    backlog_origin_result_id = fields.Many2one(
        comodel_name='edu.result.marksheet',
        string='Backlog Origin (Result)',
        ondelete='set null',
        help='The result marksheet that identified this as a backlog subject.',
    )

    # ── Notes / components ────────────────────────────────────────────────────

    remarks = fields.Text(
        string='Remarks',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='exam_paper_id.company_id',
        store=True,
    )
    component_mark_ids = fields.One2many(
        comodel_name='edu.exam.marksheet.component',
        inverse_name='marksheet_id',
        string='Component Marks',
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_paper_student_attempt',
            'UNIQUE(exam_paper_id, student_id, attempt_type, attempt_no)',
            'A marksheet for this student, attempt type and attempt number already exists for this paper.',
        ),
    ]

    # ── ORM overrides ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        """Block edits when marksheet is locked or paper is in a terminal state,
        unless the user is an admin.
        """
        is_admin = (
            self.env.user.has_group('edu_exam.group_exam_admin')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_admin:
            # Fields that are always allowed (state-tracking infra etc.)
            _always_ok = frozenset({
                'is_locked', 'verified_by', 'verified_on',
                'message_follower_ids', 'message_ids',
                'activity_ids', 'activity_state', 'activity_date_deadline',
                'activity_summary', 'activity_type_id', 'activity_user_id',
            })
            edit_fields = set(vals.keys()) - _always_ok
            if edit_fields:
                for rec in self:
                    if rec.is_locked:
                        raise UserError(
                            _('Marksheet for "%s" is locked. Unlock it before making changes.')
                            % rec.display_name
                        )
                    if rec.exam_paper_state in ('published', 'closed'):
                        raise UserError(
                            _(
                                'Marksheet for "%s" cannot be edited because the paper is in state: %s.'
                            ) % (rec.display_name, rec.exam_paper_state)
                        )
        return super().write(vals)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('student_id', 'subject_id', 'attempt_type')
    def _compute_display_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            subject = rec.subject_id.name or ''
            attempt = dict(ATTEMPT_TYPE_SELECTION).get(rec.attempt_type, '')
            parts = filter(None, [student, subject, attempt])
            rec.display_name = ' / '.join(parts) or 'New Marksheet'

    @api.depends('raw_marks', 'grace_marks', 'status')
    def _compute_final_marks(self):
        for rec in self:
            if rec.status == 'present':
                rec.final_marks = (rec.raw_marks or 0.0) + (rec.grace_marks or 0.0)
            else:
                rec.final_marks = 0.0

    @api.depends('final_marks', 'pass_marks', 'status')
    def _compute_is_pass(self):
        for rec in self:
            rec.is_pass = (
                rec.status == 'present'
                and (rec.final_marks or 0.0) >= (rec.pass_marks or 0.0)
            )

    @api.depends('attempt_type')
    def _compute_is_back_attempt(self):
        for rec in self:
            rec.is_back_attempt = rec.attempt_type in ('back', 'makeup', 'improvement', 'special')

    # ── Python constraints ────────────────────────────────────────────────────

    @api.constrains('raw_marks', 'max_marks')
    def _check_raw_marks(self):
        for rec in self:
            if (rec.raw_marks or 0.0) < 0:
                raise ValidationError(
                    _('Raw marks cannot be negative for "%s".') % rec.display_name
                )
            if rec.max_marks and (rec.raw_marks or 0.0) > rec.max_marks:
                raise ValidationError(
                    _(
                        'Raw marks (%.2f) exceed max marks (%.2f) for "%s".'
                    ) % (rec.raw_marks, rec.max_marks, rec.display_name)
                )

    @api.constrains('grace_marks')
    def _check_grace_marks(self):
        for rec in self:
            if (rec.grace_marks or 0.0) < 0:
                raise ValidationError(
                    _('Grace marks cannot be negative for "%s".') % rec.display_name
                )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_lock(self):
        """Lock this marksheet — prevent further edits."""
        for rec in self:
            rec.write({'is_locked': True})

    def action_unlock(self):
        """Unlock this marksheet — admin only."""
        is_admin = (
            self.env.user.has_group('edu_exam.group_exam_admin')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_admin:
            raise UserError(_('Only Exam Admins can unlock marksheets.'))
        for rec in self:
            rec.write({'is_locked': False})

    def action_verify(self):
        """Mark the marksheet as verified by the current user."""
        for rec in self:
            rec.write({
                'verified_by': self.env.user.id,
                'verified_on': fields.Datetime.now(),
            })

    def action_snapshot_attendance(self):
        """Fetch the attendance summary from the classroom's register and
        populate attendance_percent_snapshot and attendance_eligible.
        """
        if 'edu.attendance.register' not in self.env:
            return
        for rec in self:
            if not rec.exam_paper_id.classroom_id:
                continue
            classroom = rec.exam_paper_id.classroom_id
            register = self.env['edu.attendance.register'].search(
                [('classroom_id', '=', classroom.id)], limit=1
            )
            if not register:
                continue
            summary = register.get_student_attendance_summary()
            student_data = summary.get(rec.student_id.id)
            if student_data:
                pct = student_data.get('percent', 0.0)
                rec.write({
                    'attendance_percent_snapshot': pct,
                    'attendance_eligible': True,
                })
            else:
                rec.write({
                    'attendance_percent_snapshot': 0.0,
                    'attendance_eligible': False,
                })
