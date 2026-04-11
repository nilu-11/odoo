import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .edu_assessment_category import CATEGORY_TYPE_SELECTION

_logger = logging.getLogger(__name__)

# Fields that are safe to write regardless of lock state (chatter infra etc.)
_ALWAYS_WRITABLE = frozenset({
    'message_follower_ids', 'message_ids', 'message_partner_ids',
    'activity_ids', 'activity_state', 'activity_date_deadline',
    'activity_summary', 'activity_type_id', 'activity_user_id',
    'remarks',  # allow remarks/notes even on locked records
})

# Fields that identify the assessment outcome — locked once state='locked'
_OUTCOME_FIELDS = frozenset({
    'category_id', 'student_id', 'classroom_id', 'teacher_id',
    'assessment_date', 'max_marks', 'marks_obtained',
    'enrollment_id', 'student_progression_history_id',
    'batch_id', 'section_id', 'program_term_id',
    'subject_id', 'curriculum_line_id', 'academic_year_id',
})


class EduContinuousAssessmentRecord(models.Model):
    """Continuous Assessment Record — non-exam academic evaluation for a student.

    Covers assignments, class tests, projects, practical evaluations,
    participation, attendance-derived scores, observations, and any custom
    institutional factor.

    Academic context snapshot fields (student_progression_history_id,
    batch_id, section_id, program_term_id, etc.) are stored DIRECTLY as
    concrete columns — never only as related fields — so historical records
    remain correct after batch promotions.

    Workflow:  draft → confirmed → locked
    """

    _name = 'edu.continuous.assessment.record'
    _description = 'Continuous Assessment Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_date desc, student_id, category_id'
    _rec_name = 'display_name'

    # ── Computed display name ─────────────────────────────────────────────────

    display_name = fields.Char(
        string='Assessment',
        compute='_compute_display_name',
        store=True,
    )

    # ── Assessment identity ───────────────────────────────────────────────────

    name = fields.Char(
        string='Assessment Title',
        required=True,
        tracking=True,
        help='Descriptive title, e.g. "Assignment 1", "Class Test 3", "Project Submission".',
    )
    category_id = fields.Many2one(
        comodel_name='edu.assessment.category',
        string='Category',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    category_type = fields.Selection(
        selection=CATEGORY_TYPE_SELECTION,
        string='Category Type',
        related='category_id.category_type',
        store=True,
        index=True,
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

    # ── Snapshot fields (stored directly — NOT related — for historical correctness) ──

    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        ondelete='set null',
        index=True,
        help='Enrollment record at the time of assessment.',
    )
    student_progression_history_id = fields.Many2one(
        comodel_name='edu.student.progression.history',
        string='Progression History',
        ondelete='restrict',
        index=True,
        help='Academic progression context at the time of assessment. '
             'Preserved even after batch promotions.',
    )
    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        ondelete='restrict',
        tracking=True,
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
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        ondelete='restrict',
        index=True,
    )

    # ── Teacher ───────────────────────────────────────────────────────────────

    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )

    # ── Assessment data ───────────────────────────────────────────────────────

    assessment_date = fields.Date(
        string='Assessment Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    max_marks = fields.Float(
        string='Max Marks',
        required=True,
        default=100.0,
        tracking=True,
    )
    marks_obtained = fields.Float(
        string='Marks Obtained',
        default=0.0,
        copy=False,
        tracking=True,
    )
    percentage = fields.Float(
        string='Percentage (%)',
        compute='_compute_percentage',
        store=True,
        help='Computed as (marks_obtained / max_marks) × 100.',
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('locked', 'Locked'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Other ─────────────────────────────────────────────────────────────────

    remarks = fields.Text(
        string='Remarks',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        related='classroom_id.company_id',
        store=True,
    )

    # ── ORM overrides ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('teacher_id'):
                vals.setdefault('teacher_id', self.env.user.id)
        return super().create(vals_list)

    def write(self, vals):
        """Block edits to outcome fields when the record is locked,
        unless the current user is an Assessment Admin or Education Admin.
        """
        is_admin = (
            self.env.user.has_group('edu_assessment.group_assessment_admin')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_admin:
            edit_fields = set(vals.keys()) - _ALWAYS_WRITABLE
            if edit_fields:
                locked = self.filtered(lambda r: r.state == 'locked')
                if locked:
                    names = ', '.join(locked[:3].mapped('display_name'))
                    raise UserError(
                        _(
                            'Assessment record(s) "%s" are locked and cannot be edited. '
                            'Ask an admin to reset them if a correction is needed.'
                        ) % names
                    )
        return super().write(vals)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('name', 'student_id', 'category_id')
    def _compute_display_name(self):
        for rec in self:
            student = rec.student_id.display_name or ''
            cat = rec.category_id.name or ''
            title = rec.name or ''
            parts = filter(None, [student, cat, title])
            rec.display_name = ' / '.join(parts) or 'New Assessment'

    @api.depends('marks_obtained', 'max_marks')
    def _compute_percentage(self):
        for rec in self:
            if rec.max_marks and rec.max_marks > 0:
                rec.percentage = round((rec.marks_obtained or 0.0) / rec.max_marks * 100, 2)
            else:
                rec.percentage = 0.0

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('marks_obtained', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if (rec.max_marks or 0.0) <= 0:
                raise ValidationError(
                    _('Max marks must be greater than zero for "%s".') % rec.display_name
                )
            if (rec.marks_obtained or 0.0) < 0:
                raise ValidationError(
                    _('Marks obtained cannot be negative for "%s".') % rec.display_name
                )
            if (rec.marks_obtained or 0.0) > (rec.max_marks or 0.0):
                raise ValidationError(
                    _(
                        'Marks obtained (%.2f) cannot exceed max marks (%.2f) for "%s".'
                    ) % (rec.marks_obtained, rec.max_marks, rec.display_name)
                )

    # ── Onchange — classroom auto-populate ────────────────────────────────────

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        if self.classroom_id:
            cl = self.classroom_id
            self.section_id = cl.section_id
            self.batch_id = cl.batch_id
            self.program_term_id = cl.program_term_id
            self.curriculum_line_id = cl.curriculum_line_id
            self.subject_id = cl.subject_id
            if not self.teacher_id or self.teacher_id == self.env.user:
                self.teacher_id = cl.teacher_id or self.env.user
            # Derive academic_year from program_term if available
            if cl.program_term_id and cl.program_term_id.academic_year_id:
                self.academic_year_id = cl.program_term_id.academic_year_id

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id and not self.max_marks:
            self.max_marks = self.category_id.default_max_marks or 100.0

    @api.onchange('student_id')
    def _onchange_student_id(self):
        """Auto-populate progression history and enrollment from the student's
        active progression history when classroom context is already set.
        """
        if not self.student_id:
            self.student_progression_history_id = False
            self.enrollment_id = False
            return

        # Try to find the active progression history
        domain = [
            ('student_id', '=', self.student_id.id),
            ('state', '=', 'active'),
        ]
        if self.section_id:
            domain.append(('section_id', '=', self.section_id.id))
        history = self.env['edu.student.progression.history'].search(domain, limit=1)
        if history:
            self.student_progression_history_id = history
            self.enrollment_id = history.enrollment_id
            if not self.batch_id:
                self.batch_id = history.batch_id
            if not self.section_id:
                self.section_id = history.section_id
            if not self.program_term_id:
                self.program_term_id = history.program_term_id
            if not self.academic_year_id:
                self.academic_year_id = history.academic_year_id

    # ── State transitions ────────────────────────────────────────────────────

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _('Only Draft assessment records can be confirmed. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
        self.write({'state': 'confirmed'})

    def action_lock(self):
        """Lock — prevent further edits to assessment data."""
        for rec in self:
            if rec.state not in ('draft', 'confirmed'):
                raise UserError(
                    _('Assessment record "%s" is already locked or in an invalid state.')
                    % rec.display_name
                )
        self.write({'state': 'locked'})

    def action_reset_draft(self):
        """Admin-only reset: locked/confirmed → draft."""
        is_admin = (
            self.env.user.has_group('edu_assessment.group_assessment_admin')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_admin:
            raise UserError(_('Only Assessment Admins can reset locked records.'))
        for rec in self:
            if rec.state not in ('locked', 'confirmed'):
                raise UserError(
                    _('Only Locked or Confirmed records can be reset to Draft. '
                      '"%s" is in state: %s.') % (rec.display_name, rec.state)
                )
        self.write({'state': 'draft'})

    # ── Smart button / classroom action ──────────────────────────────────────

    def action_snapshot_attendance(self):
        """If edu_attendance is installed, fetch the student's attendance
        percentage from the classroom register and suggest marks_obtained
        (proportional to max_marks).  Does NOT auto-save — teacher reviews first.
        """
        self.ensure_one()
        if 'edu.attendance.register' not in self.env:
            raise UserError(
                _('The attendance module is not installed. '
                  'Enter the attendance score manually.')
            )
        if not self.classroom_id:
            raise UserError(
                _('Set a classroom before snapshotting attendance.')
            )
        register = self.env['edu.attendance.register'].search(
            [('classroom_id', '=', self.classroom_id.id)], limit=1
        )
        if not register:
            raise UserError(
                _('No attendance register found for classroom "%s".')
                % self.classroom_id.name
            )
        summary = register.get_student_attendance_summary()
        student_data = summary.get(self.student_id.id)
        if not student_data:
            raise UserError(
                _('No attendance data found for student "%s" in classroom "%s".')
                % (self.student_id.display_name, self.classroom_id.name)
            )
        pct = student_data.get('percent', 0.0)
        suggested_marks = round(pct / 100.0 * (self.max_marks or 100.0), 2)
        self.write({'marks_obtained': suggested_marks})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Attendance Snapshot'),
                'message': _(
                    'Attendance: %.1f%%. Suggested marks set to %.2f / %.2f.'
                ) % (pct, suggested_marks, self.max_marks),
                'type': 'success',
                'sticky': False,
            },
        }
