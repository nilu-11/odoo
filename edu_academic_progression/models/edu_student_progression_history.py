import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class EduStudentProgressionHistory(models.Model):
    """One record per student per academic progression period.

    This is the historical anchor for all future academic modules. Attendance,
    exam results, assignments, and timetable records should link back to this
    model via student_progression_history_id to ensure correct semester-scoped
    reporting even after the student advances to the next progression.
    """
    _name = 'edu.student.progression.history'
    _description = 'Student Academic Progression History'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, student_id, id desc'
    _rec_name = 'display_name'

    # ── Identity ──────────────────────────────────────────────────────────────

    student_id = fields.Many2one(
        'edu.student', string='Student',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )
    enrollment_id = fields.Many2one(
        'edu.enrollment', string='Enrollment',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )

    # ── Academic Context (frozen after closure) ───────────────────────────────

    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )
    program_id = fields.Many2one(
        'edu.program', string='Program',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )
    academic_year_id = fields.Many2one(
        'edu.academic.year', string='Academic Year',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )
    program_term_id = fields.Many2one(
        'edu.program.term', string='Progression / Term',
        required=True, ondelete='restrict',
        index=True, tracking=True,
    )
    section_id = fields.Many2one(
        'edu.section', string='Section',
        ondelete='set null',
        index=True, tracking=True,
    )

    # ── Derived / Stored Relateds ─────────────────────────────────────────────

    department_id = fields.Many2one(
        'edu.department',
        related='program_id.department_id',
        store=True, index=True, string='Department',
    )
    progression_no = fields.Integer(
        related='program_term_id.progression_no',
        store=True, string='Progression No',
    )
    progression_label = fields.Char(
        related='program_term_id.progression_label',
        store=True, string='Progression Label',
    )
    company_id = fields.Many2one(
        'res.company',
        related='program_id.company_id',
        store=True, index=True,
    )

    # ── Period ────────────────────────────────────────────────────────────────

    start_date = fields.Date(
        string='Start Date',
        required=True, tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection([
        ('active',    'Active'),
        ('completed', 'Completed'),
        ('promoted',  'Promoted'),
        ('repeated',  'Repeated'),
        ('cancelled', 'Cancelled'),
    ], string='State', required=True, default='active',
       tracking=True, index=True, copy=False,
    )

    # ── Promotion Chain ───────────────────────────────────────────────────────

    promoted_from_id = fields.Many2one(
        'edu.student.progression.history',
        string='Promoted From', readonly=True,
        copy=False, ondelete='set null',
        help='The progression record this one was created from during batch promotion.',
    )
    promoted_to_id = fields.Many2one(
        'edu.student.progression.history',
        string='Promoted To', readonly=True,
        copy=False, ondelete='set null',
        help='The progression record created when this one was closed by promotion.',
    )

    # ── Audit ─────────────────────────────────────────────────────────────────

    closed_by_user_id = fields.Many2one(
        'res.users', string='Closed By',
        readonly=True, copy=False,
    )
    closed_on = fields.Datetime(
        string='Closed On',
        readonly=True, copy=False,
    )
    # ── Elective Subject Choices ───────────────────────────────────────────

    elected_curriculum_line_ids = fields.Many2many(
        comodel_name='edu.curriculum.line',
        relation='edu_progression_elected_curriculum_rel',
        column1='progression_history_id',
        column2='curriculum_line_id',
        string='Elected Subjects',
        domain="[('program_term_id', '=', program_term_id), ('subject_category', 'in', ('elective', 'optional'))]",
        help='Elective and optional subjects the student has chosen for this term. '
             'Mandatory subjects are always included automatically.',
    )

    effective_curriculum_line_ids = fields.Many2many(
        comodel_name='edu.curriculum.line',
        relation='edu_progression_effective_curriculum_rel',
        column1='progression_history_id',
        column2='curriculum_line_id',
        string='Effective Subjects (Mandatory + Elected)',
        compute='_compute_effective_curriculum_lines',
        store=True,
    )
    # ── Notes ─────────────────────────────────────────────────────────────────

    remarks = fields.Text(string='Remarks')

    # ── Display ───────────────────────────────────────────────────────────────

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True, precompute=True,
    )

    # ── Module Constants ──────────────────────────────────────────────────────

    _CLOSED_STATES = frozenset({'completed', 'promoted', 'repeated', 'cancelled'})
    # Fields that become read-only once the record is in a closed state.
    _FROZEN_FIELDS = frozenset({
        'student_id', 'enrollment_id', 'batch_id', 'program_id',
        'academic_year_id', 'program_term_id', 'start_date', 'end_date',
        'elected_curriculum_line_ids',
    })

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends(
        'student_id.student_no',
        'batch_id.name',
        'program_term_id.progression_label',
        'program_term_id.name',
        'state',
    )
    def _compute_display_name(self):
        for rec in self:
            parts = [
                rec.student_id.student_no or '',
                rec.batch_id.name or '',
                rec.program_term_id.progression_label or rec.program_term_id.name or '',
            ]
            label = ' | '.join(p for p in parts if p)
            rec.display_name = (
                '[%s] %s' % (rec.state, label) if label else _('Progression Record')
            )
    @api.depends('program_term_id', 'elected_curriculum_line_ids')
    def _compute_effective_curriculum_lines(self):
        CurriculumLine = self.env['edu.curriculum.line']
        for rec in self:
            if not rec.program_term_id:
                rec.effective_curriculum_line_ids = CurriculumLine
                continue
            mandatory = CurriculumLine.search([
                ('program_term_id', '=', rec.program_term_id.id),
                ('subject_category', '=', 'compulsory'),
            ])
            rec.effective_curriculum_line_ids = mandatory | rec.elected_curriculum_line_ids
    # ── ORM Overrides ─────────────────────────────────────────────────────────

    def write(self, vals):
        """Prevent modification of frozen fields on closed records."""
        for rec in self:
            if rec.state in self._CLOSED_STATES:
                attempted = set(vals.keys()) & self._FROZEN_FIELDS
                if attempted:
                    raise ValidationError(_(
                        'Progression record "%s" is closed (state: %s). '
                        'The following fields are locked and cannot be modified: %s'
                    ) % (rec.display_name, rec.state, ', '.join(sorted(attempted))))
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of closed progression records."""
        for rec in self:
            if rec.state in self._CLOSED_STATES:
                raise UserError(_(
                    'Closed progression records cannot be deleted: '
                    '"%s" (state: %s). Archive it if you need to hide it.'
                ) % (rec.display_name, rec.state))
        return super().unlink()

    # ── Python Constraints ────────────────────────────────────────────────────

    @api.constrains('student_id', 'state')
    def _check_unique_active_per_student(self):
        """Enforce: at most one active progression record per student."""
        for rec in self:
            if rec.state == 'active':
                conflict = self.search([
                    ('student_id', '=', rec.student_id.id),
                    ('state', '=', 'active'),
                    ('id', '!=', rec.id),
                ], limit=1)
                if conflict:
                    raise ValidationError(_(
                        'Student "%s" already has an active progression record (ID %d). '
                        'Close the existing record before activating another one.'
                    ) % (rec.student_id.display_name, conflict.id))

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_(
                    'End date (%s) cannot be earlier than start date (%s) '
                    'on progression record "%s".'
                ) % (rec.end_date, rec.start_date, rec.display_name))

    @api.constrains('program_term_id', 'program_id')
    def _check_term_belongs_to_program(self):
        for rec in self:
            if rec.program_term_id and rec.program_id:
                if rec.program_term_id.program_id != rec.program_id:
                    raise ValidationError(_(
                        'Progression term "%s" does not belong to program "%s".'
                    ) % (rec.program_term_id.name, rec.program_id.name))

    @api.constrains('batch_id', 'program_id')
    def _check_batch_belongs_to_program(self):
        for rec in self:
            if rec.batch_id and rec.program_id:
                if rec.batch_id.program_id != rec.program_id:
                    raise ValidationError(_(
                        'Batch "%s" does not belong to program "%s".'
                    ) % (rec.batch_id.name, rec.program_id.name))

    @api.constrains('elected_curriculum_line_ids', 'program_term_id')
    def _check_elected_belong_to_term(self):
        for rec in self:
            for line in rec.elected_curriculum_line_ids:
                if line.program_term_id != rec.program_term_id:
                    raise ValidationError(
                        _('Subject "%s" does not belong to the selected program term.')
                        % line.subject_id.name
                    )
                if line.subject_category == 'compulsory':
                    raise ValidationError(
                        _('Subject "%s" is compulsory and cannot be added as an elective choice.')
                        % line.subject_id.name
                    )

    @api.constrains('section_id', 'batch_id')
    def _check_section_belongs_to_batch(self):
        for rec in self:
            if rec.section_id and rec.batch_id:
                if rec.section_id.batch_id != rec.batch_id:
                    raise ValidationError(_(
                        'Section "%s" does not belong to batch "%s".'
                    ) % (rec.section_id.name, rec.batch_id.name))

    # ── Closure API (called by wizard) ────────────────────────────────────────

    def _close_for_promotion(self, end_date):
        """Mark this record as promoted. Called by the batch promotion wizard.

        Must be called before creating the replacement record to avoid
        triggering the unique-active-per-student constraint.
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_(
                'Cannot close progression "%s": '
                'expected state "active", found "%s".'
            ) % (self.display_name, self.state))
        self.write({
            'state': 'promoted',
            'end_date': end_date,
            'closed_by_user_id': self.env.user.id,
            'closed_on': fields.Datetime.now(),
        })

    def action_cancel(self):
        """Admin: cancel an active progression record without a promotion."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active progression records can be cancelled.'))
        self.write({
            'state': 'cancelled',
            'closed_by_user_id': self.env.user.id,
            'closed_on': fields.Datetime.now(),
        })
        self.message_post(
            body=_('Progression cancelled by <b>%s</b>.') % self.env.user.name,
            subtype_xmlid='mail.mt_note',
        )

    # ── Public Helpers for downstream modules ────────────────────────────────

    def get_academic_context(self):
        """Return the full academic context dict for downstream record linking.

        Future modules (attendance, exams, assignments, timetable) should call
        this on the student's active or historical progression record to anchor
        their records to the correct progression period::

            context = student._get_active_progression_history().get_academic_context()
            attendance_vals.update(context)

        The dict always contains 'student_progression_history_id' as the primary
        foreign key future modules should store.
        """
        self.ensure_one()
        return {
            'student_progression_history_id': self.id,
            'student_id': self.student_id.id,
            'enrollment_id': self.enrollment_id.id,
            'batch_id': self.batch_id.id,
            'program_id': self.program_id.id,
            'academic_year_id': self.academic_year_id.id,
            'program_term_id': self.program_term_id.id,
            'section_id': self.section_id.id if self.section_id else False,
        }
