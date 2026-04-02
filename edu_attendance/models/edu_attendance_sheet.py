import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EduAttendanceSheet(models.Model):
    """One attendance session for a classroom.

    A sheet is tied to a register (and thus a classroom).  Teachers start a
    session, which auto-populates student lines from the active progression
    histories for the section.

    State flow:  draft → in_progress → submitted
    Admin can reset submitted → draft.
    """

    _name = 'edu.attendance.sheet'
    _description = 'Attendance Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc, time_from desc'
    _rec_name = 'display_name'

    # ── Display ───────────────────────────────────────────────────────────────

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True,
        precompute=True,
    )

    # ── Core FK ───────────────────────────────────────────────────────────────

    register_id = fields.Many2one(
        comodel_name='edu.attendance.register',
        string='Register',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    # ── Stored related fields from register ───────────────────────────────────

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        related='register_id.classroom_id',
        store=True,
        index=True,
        string='Classroom',
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        related='register_id.section_id',
        store=True,
        index=True,
        string='Section',
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        related='register_id.subject_id',
        store=True,
        index=True,
        string='Subject',
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        related='register_id.batch_id',
        store=True,
        index=True,
        string='Batch',
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        related='register_id.program_term_id',
        store=True,
        index=True,
        string='Program Term',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        related='register_id.academic_year_id',
        store=True,
        index=True,
        string='Academic Year',
    )
    teacher_id = fields.Many2one(
        comodel_name='res.users',
        related='register_id.teacher_id',
        store=True,
        index=True,
        string='Teacher',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='register_id.company_id',
        store=True,
        index=True,
    )

    # ── Session details ───────────────────────────────────────────────────────

    session_date = fields.Date(
        string='Session Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    time_from = fields.Float(
        string='From',
        help='Start time in decimal hours (e.g. 9.5 = 09:30)',
        tracking=True,
    )
    time_to = fields.Float(
        string='To',
        help='End time in decimal hours (e.g. 11.0 = 11:00)',
        tracking=True,
    )
    taken_by = fields.Many2one(
        comodel_name='res.users',
        string='Taken By',
        default=lambda self: self.env.user,
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('submitted', 'Submitted'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Lines ─────────────────────────────────────────────────────────────────

    line_ids = fields.One2many(
        comodel_name='edu.attendance.sheet.line',
        inverse_name='sheet_id',
        string='Attendance Lines',
    )
    line_count = fields.Integer(
        string='Students',
        compute='_compute_counts',
        store=False,
    )
    present_count = fields.Integer(
        string='Present',
        compute='_compute_counts',
        store=False,
    )
    absent_count = fields.Integer(
        string='Absent',
        compute='_compute_counts',
        store=False,
    )

    # ── Locking constants ─────────────────────────────────────────────────────

    _LOCKED_FIELDS = frozenset({'session_date', 'time_from', 'time_to', 'register_id', 'taken_by'})

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('register_id.name', 'session_date')
    def _compute_display_name(self):
        for rec in self:
            date_str = str(rec.session_date) if rec.session_date else ''
            reg_name = rec.register_id.name or ''
            rec.display_name = ('%s — %s' % (reg_name, date_str)) if date_str else reg_name

    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.present_count = sum(
                1 for l in rec.line_ids if l.status in ('present', 'late')
            )
            rec.absent_count = sum(
                1 for l in rec.line_ids if l.status == 'absent'
            )

    # ── Constraints ───────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'register_date_time_unique',
            'UNIQUE(register_id, session_date, time_from)',
            'An attendance sheet already exists for this classroom on this '
            'date and time slot. Use the existing sheet instead.',
        ),
    ]

    @api.constrains('register_id', 'session_date', 'time_from')
    def _check_duplicate_sheet(self):
        """Prevent duplicate sheets for the same register + date (+ time slot)."""
        for rec in self:
            domain = [
                ('register_id', '=', rec.register_id.id),
                ('session_date', '=', rec.session_date),
                ('id', '!=', rec.id),
            ]
            if rec.time_from:
                domain.append(('time_from', '=', rec.time_from))
            else:
                domain.append(('time_from', '=', False))
            if self.env['edu.attendance.sheet'].search_count(domain):
                raise ValidationError(_(
                    'An attendance sheet already exists for "%s" on %s%s. '
                    'Please use the existing sheet instead of creating a new one.'
                ) % (
                    rec.register_id.name,
                    rec.session_date,
                    (' at %.2f' % rec.time_from) if rec.time_from else '',
                ))

    @api.constrains('time_from', 'time_to')
    def _check_times(self):
        for rec in self:
            if rec.time_from and rec.time_to and rec.time_to <= rec.time_from:
                raise ValidationError(_(
                    'End time must be after start time on sheet "%s".'
                ) % rec.display_name)

    @api.constrains('register_id')
    def _check_register_open(self):
        for rec in self:
            if rec.register_id and rec.register_id.state == 'closed':
                raise ValidationError(_(
                    'Cannot add sheets to closed register "%s".'
                ) % rec.register_id.name)

    # ── State transitions ─────────────────────────────────────────────────────

    def action_start(self):
        """draft → in_progress; auto-generates lines if none exist."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Sheet "%s" is not in draft state.'
                ) % rec.display_name)
            if rec.register_id.state == 'closed':
                raise UserError(_(
                    'Cannot start a session — register "%s" is closed.'
                ) % rec.register_id.name)
        self.write({'state': 'in_progress'})
        for rec in self:
            if not rec.line_ids:
                rec.action_generate_lines()

    def action_generate_lines(self):
        """Populate lines from active progression histories for the section/term."""
        self.ensure_one()
        if self.state == 'submitted':
            raise UserError(_(
                'Cannot regenerate lines on a submitted sheet "%s".'
            ) % self.display_name)

        domain = [
            ('section_id', '=', self.section_id.id),
            ('state', '=', 'active'),
        ]
        if self.program_term_id:
            domain.append(('program_term_id', '=', self.program_term_id.id))
        histories = self.env['edu.student.progression.history'].search(domain)
        if not histories:
            return

        existing_student_ids = set(self.line_ids.mapped('student_id').ids)
        vals_list = [
            {
                'sheet_id': self.id,
                'student_id': hist.student_id.id,
                'student_progression_history_id': hist.id,
                'status': 'present',
            }
            for hist in histories
            if hist.student_id.id not in existing_student_ids
        ]
        if vals_list:
            self.env['edu.attendance.sheet.line'].create(vals_list)

    def action_submit(self):
        """in_progress → submitted."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_(
                    'Only in-progress sheets can be submitted. '
                    'Sheet "%s" is currently "%s".'
                ) % (rec.display_name, rec.state))
            if not rec.line_ids:
                raise UserError(_(
                    'Cannot submit sheet "%s" — no attendance lines recorded.'
                ) % rec.display_name)
        self.write({'state': 'submitted'})

    def action_mark_all_present(self):
        """Set all attendance lines to 'present' (quick reset)."""
        for rec in self:
            if rec.state == 'submitted':
                raise UserError(_(
                    'Cannot modify submitted sheet "%s". '
                    'Reset it to draft first.'
                ) % rec.display_name)
            lines = rec.line_ids.filtered(lambda l: l.status != 'present')
            if lines:
                lines.write({'status': 'present'})

    def action_reset_to_draft(self):
        """Admin only: submitted → draft."""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted sheets can be reset to draft.'))
        self.write({'state': 'draft'})

    # ── ORM override ──────────────────────────────────────────────────────────

    def write(self, vals):
        """Lock session-identity fields on submitted sheets."""
        if set(vals.keys()) & self._LOCKED_FIELDS:
            submitted = self.filtered(lambda r: r.state == 'submitted')
            if submitted:
                raise UserError(_(
                    'Cannot edit a submitted attendance sheet. '
                    'Reset it to draft first.'
                ))
        return super().write(vals)
