import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EduClassroom(models.Model):
    """Classroom — one subject being taught to one section in one program term.

    This is the central hub for Phase 7.5 of the EMIS system.  Every classroom
    record ties together:
      - a Batch + Section  (the cohort of students)
      - a Program Term     (the progression stage / semester)
      - a Curriculum Line  (the specific subject in that term)
      - a Teacher          (the assigned instructor)

    Downstream modules (edu_attendance, edu_exams, edu_assignments) should
    link their records to ``edu.classroom`` via a Many2one so that all
    subject-scoped reporting stays properly anchored.

    The ``_generate_classrooms_for_section`` class method provides an
    idempotent way to bulk-create all classrooms for a section in a term
    from the batch / section allocation wizard (Phase 8).
    """

    _name = 'edu.classroom'
    _description = 'Classroom — Subject × Section'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'batch_id, section_id, program_term_id'
    _rec_name = 'name'

    # ── Module-level constants ────────────────────────────────────────────────

    _ACTIVE_CLOSED = frozenset({'active', 'closed'})

    # Fields that cannot be changed once the classroom is active or closed.
    _LOCKED_FIELDS = frozenset({
        'section_id', 'curriculum_line_id', 'batch_id', 'program_term_id',
    })

    # Fields that are always writable regardless of state.
    _ALWAYS_UNLOCKED = frozenset({
        'state', 'teacher_id', 'notes', 'active',
        'attendance_register_id',
        'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })

    # ── Identity / Computed ───────────────────────────────────────────────────

    name = fields.Char(
        string='Classroom Name',
        compute='_compute_name',
        store=True,
        readonly=False,
        tracking=True,
        help='Auto-computed from batch, section, subject, and term. Editable.',
    )
    code = fields.Char(
        string='Code',
        compute='_compute_code',
        store=True,
        readonly=False,
        help='Auto-computed short code. Editable.',
    )

    # ── Core FK fields ────────────────────────────────────────────────────────

    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('batch_id', '=', batch_id)]",
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='edu.curriculum.line',
        string='Curriculum Line',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('program_term_id', '=', program_term_id)]",
    )

    # ── Stored related fields ─────────────────────────────────────────────────

    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        related='curriculum_line_id.subject_id',
        string='Subject',
        store=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        related='batch_id.academic_year_id',
        string='Academic Year',
        store=True,
        index=True,
    )
    program_id = fields.Many2one(
        comodel_name='edu.program',
        related='batch_id.program_id',
        string='Program',
        store=True,
        index=True,
    )
    department_id = fields.Many2one(
        comodel_name='edu.department',
        related='program_id.department_id',
        string='Department',
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='batch_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── Assignment ────────────────────────────────────────────────────────────

    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
        ondelete='set null',
        tracking=True,
        index=True,
    )

    # ── State / Flags ─────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    # ── Misc ──────────────────────────────────────────────────────────────────

    notes = fields.Text(string='Notes')

    # ── Computed counts ───────────────────────────────────────────────────────

    student_count = fields.Integer(
        string='Students',
        compute='_compute_student_count',
        store=False,
    )
    attendance_count = fields.Integer(
        string='Sessions',
        compute='_compute_attendance_count',
        store=False,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'section_curriculum_unique',
            'UNIQUE(section_id, curriculum_line_id)',
            'A classroom for this subject already exists in this section.',
        ),
    ]

    # ── Computed: name ────────────────────────────────────────────────────────

    @api.depends(
        'batch_id.code',
        'section_id.name',
        'subject_id.code',
        'program_term_id.progression_label',
    )
    def _compute_name(self):
        for rec in self:
            parts = [
                rec.batch_id.code or '',
                rec.section_id.name or '',
                rec.subject_id.code or '',
                rec.program_term_id.progression_label or '',
            ]
            rec.name = ' / '.join(p for p in parts if p) or False

    # ── Computed: code ────────────────────────────────────────────────────────

    @api.depends('batch_id.code', 'section_id.name', 'subject_id.code')
    def _compute_code(self):
        for rec in self:
            batch_code = (rec.batch_id.code or '').upper().replace(' ', '')
            sec_name = (rec.section_id.name or '').upper().replace(' ', '')
            subj_code = (rec.subject_id.code or '').upper().replace(' ', '')
            parts = [p for p in [batch_code, sec_name, subj_code] if p]
            rec.code = '-'.join(parts) or False

    # ── Computed: student_count ───────────────────────────────────────────────

    def _compute_student_count(self):
        """Count students via active progression history records for the section."""
        ProgressionHistory = self.env['edu.student.progression.history']
        section_ids = self.mapped('section_id').ids
        if not section_ids:
            for rec in self:
                rec.student_count = 0
            return

        data = ProgressionHistory._read_group(
            domain=[
                ('section_id', 'in', section_ids),
                ('state', '=', 'active'),
            ],
            groupby=['section_id'],
            aggregates=['__count'],
        )
        mapped = {section.id: count for section, count in data}
        for rec in self:
            rec.student_count = mapped.get(rec.section_id.id, 0)

    # ── Computed: attendance_count ────────────────────────────────────────────

    def _compute_attendance_count(self):
        """Count attendance sheets if edu_attendance is installed, else 0."""
        if 'edu.attendance.sheet' not in self.env:
            for rec in self:
                rec.attendance_count = 0
            return

        AttSheet = self.env['edu.attendance.sheet']
        # attendance_register_id is injected by edu_attendance via _inherit;
        # use getattr so this module can still load without edu_attendance.
        register_ids = [
            r.id
            for rec in self
            for r in [getattr(rec, 'attendance_register_id', False)]
            if r
        ]
        if not register_ids:
            for rec in self:
                rec.attendance_count = 0
            return

        data = AttSheet._read_group(
            domain=[('register_id', 'in', register_ids)],
            groupby=['register_id'],
            aggregates=['__count'],
        )
        mapped = {reg.id: count for reg, count in data}
        for rec in self:
            reg_id = getattr(rec, 'attendance_register_id', False)
            reg_id = reg_id.id if reg_id else False
            rec.attendance_count = mapped.get(reg_id, 0) if reg_id else 0

    # ── Python constraints ────────────────────────────────────────────────────

    @api.constrains('section_id', 'batch_id')
    def _check_section_in_batch(self):
        for rec in self:
            if rec.section_id and rec.batch_id:
                if rec.section_id.batch_id != rec.batch_id:
                    raise ValidationError(_(
                        'Section "%s" does not belong to batch "%s".'
                    ) % (rec.section_id.name, rec.batch_id.name))

    @api.constrains('curriculum_line_id', 'program_term_id')
    def _check_curriculum_in_term(self):
        for rec in self:
            if rec.curriculum_line_id and rec.program_term_id:
                if rec.curriculum_line_id.program_term_id != rec.program_term_id:
                    raise ValidationError(_(
                        'Curriculum line "%s" does not belong to program term "%s".'
                    ) % (rec.curriculum_line_id.display_name, rec.program_term_id.name))

    @api.constrains('program_term_id', 'batch_id')
    def _check_term_in_program(self):
        for rec in self:
            if rec.program_term_id and rec.batch_id:
                if rec.program_term_id.program_id != rec.batch_id.program_id:
                    raise ValidationError(_(
                        'Program term "%s" does not belong to the program '
                        'of batch "%s".'
                    ) % (rec.program_term_id.name, rec.batch_id.name))

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        """Clear dependent fields when the batch changes."""
        self.section_id = False
        self.program_term_id = False
        self.curriculum_line_id = False

    @api.onchange('program_term_id')
    def _onchange_program_term_id(self):
        """Clear curriculum line when the program term changes."""
        self.curriculum_line_id = False

    # ── State transitions ─────────────────────────────────────────────────────

    def action_activate(self):
        """Transition draft → active. Validates batch state and creates register."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Classroom "%s" is not in draft state.'
                ) % rec.name)
            if rec.batch_id.state != 'active':
                raise UserError(_(
                    'Cannot activate classroom "%s" — '
                    'batch "%s" is not active.'
                ) % (rec.name, rec.batch_id.name))
        self.write({'state': 'active'})
        for rec in self:
            rec._ensure_attendance_register()

    def action_close(self):
        """Transition active → closed."""
        for rec in self:
            if rec.state != 'active':
                raise UserError(_(
                    'Only active classrooms can be closed.'
                ))
            # Guard: no in-progress attendance sheets
            register = getattr(rec, 'attendance_register_id', False)
            if 'edu.attendance.sheet' in self.env and register:
                in_progress = self.env['edu.attendance.sheet'].search_count([
                    ('register_id', '=', register.id),
                    ('state', '=', 'in_progress'),
                ])
                if in_progress:
                    raise UserError(_(
                        'Cannot close classroom "%s" — '
                        'there are attendance sheets still in progress.'
                    ) % rec.name)
            # Close linked attendance register if it exists
            if (
                'edu.attendance.register' in self.env
                and register
                and hasattr(register, 'action_close')
            ):
                try:
                    register.action_close()
                except Exception as e:
                    _logger.warning(
                        'Could not close attendance register for classroom %s: %s',
                        rec.name, e,
                    )
        self.write({'state': 'closed'})

    def action_draft(self):
        """Admin only: reset closed → draft. Blocks if submitted attendance sheets exist."""
        for rec in self:
            if rec.state != 'closed':
                raise UserError(_(
                    'Only closed classrooms can be reset to draft.'
                ))
            register = getattr(rec, 'attendance_register_id', False)
            if 'edu.attendance.sheet' in self.env and register:
                submitted = self.env['edu.attendance.sheet'].search_count([
                    ('register_id', '=', register.id),
                    ('state', '=', 'submitted'),
                ])
                if submitted:
                    raise UserError(_(
                        'Cannot reset classroom "%s" to draft — '
                        'submitted attendance sheets exist.'
                    ) % rec.name)
        self.write({'state': 'draft'})

    # ── Attendance register helper ────────────────────────────────────────────

    def _ensure_attendance_register(self):
        """Idempotently create an attendance register for this classroom.

        Does nothing if ``edu.attendance.register`` is not installed or if a
        register is already linked.  Called automatically when activating a
        classroom; safe to call multiple times.
        """
        self.ensure_one()
        if 'edu.attendance.register' not in self.env:
            return
        # attendance_register_id is injected by edu_attendance via _inherit
        if getattr(self, 'attendance_register_id', False):
            return
        try:
            register = self.env['edu.attendance.register'].create({
                'classroom_id': self.id,
                'name': self.name or self.code,
                'batch_id': self.batch_id.id,
                'section_id': self.section_id.id,
                'program_term_id': self.program_term_id.id,
                'subject_id': self.subject_id.id,
                'teacher_id': self.teacher_id.id if self.teacher_id else False,
            })
            # Use super().write to bypass our own identity-lock guard
            super(EduClassroom, self).write({'attendance_register_id': register.id})
        except Exception as e:
            _logger.warning(
                'Could not create attendance register for classroom %s: %s',
                self.name, e,
            )

    # ── Bulk generate classrooms for a section ────────────────────────────────

    @api.model
    def _generate_classrooms_for_section(self, section, program_term):
        """Create one classroom per curriculum line for the given section/term.

        Idempotent: skips lines where a classroom already exists.

        :param section: ``edu.section`` record
        :param program_term: ``edu.program.term`` record
        :returns: newly created ``edu.classroom`` recordset
        """
        created = self.env['edu.classroom']
        for line in program_term.curriculum_line_ids:
            existing = self.search([
                ('section_id', '=', section.id),
                ('curriculum_line_id', '=', line.id),
            ], limit=1)
            if existing:
                continue
            classroom = self.create({
                'batch_id': section.batch_id.id,
                'section_id': section.id,
                'program_term_id': program_term.id,
                'curriculum_line_id': line.id,
            })
            created |= classroom
        return created

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_students(self):
        """Open student list filtered to the students in this classroom's section."""
        self.ensure_one()
        histories = self.env['edu.student.progression.history'].search([
            ('section_id', '=', self.section_id.id),
            ('state', '=', 'active'),
        ])
        student_ids = histories.mapped('student_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Students — %s') % self.name,
            'res_model': 'edu.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', student_ids)],
            'context': {},
        }

    def action_view_attendance_register(self):
        """Open the linked attendance register (create it first if needed)."""
        self.ensure_one()
        register = getattr(self, 'attendance_register_id', False)
        if not register:
            self._ensure_attendance_register()
            register = getattr(self, 'attendance_register_id', False)
        if not register:
            raise UserError(_(
                'No attendance register is linked to this classroom '
                'and edu_attendance is not installed.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attendance Register — %s') % self.name,
            'res_model': 'edu.attendance.register',
            'view_mode': 'form',
            'res_id': register.id,
        }

    # ── ORM overrides ─────────────────────────────────────────────────────────

    def write(self, vals):
        """Lock identity fields once the classroom is active or closed."""
        changing = set(vals.keys())
        locked_being_changed = changing & self._LOCKED_FIELDS
        if locked_being_changed:
            locked_recs = self.filtered(lambda r: r.state in self._ACTIVE_CLOSED)
            if locked_recs:
                raise UserError(_(
                    'Cannot modify %s on classroom "%s" — '
                    'the classroom is %s. '
                    'Allowed changes are: teacher, notes, and status.'
                ) % (
                    ', '.join(sorted(locked_being_changed)),
                    locked_recs[0].name,
                    locked_recs[0].state,
                ))
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of active or closed classrooms."""
        for rec in self:
            if rec.state in self._ACTIVE_CLOSED:
                raise UserError(_(
                    'Cannot delete classroom "%s" — it is %s. '
                    'Archive it instead.'
                ) % (rec.name, rec.state))
        return super().unlink()
