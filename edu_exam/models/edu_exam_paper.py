import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EduExamPaper(models.Model):
    """Exam Paper — one subject's examination within an exam session.

    A paper is scoped to a single curriculum line (subject) and section.
    It carries the marks configuration (max/pass marks, components) and owns
    the marksheets for all students sitting that paper.

    When linked to a classroom, the paper auto-derives section, program_term,
    curriculum_line, and teacher from the classroom context.

    Workflow: draft → scheduled → in_progress → marks_entry → submitted → published → closed
    """

    _name = 'edu.exam.paper'
    _description = 'Exam Paper'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_session_id, section_id, subject_id'
    _rec_name = 'display_name'

    # ── Computed display name ─────────────────────────────────────────────────

    display_name = fields.Char(
        string='Paper',
        compute='_compute_display_name',
        store=True,
    )

    # ── Session link ──────────────────────────────────────────────────────────

    exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Exam Session',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    exam_session_state = fields.Selection(
        related='exam_session_id.state',
        string='Session State',
        store=True,
        index=True,
    )

    # ── Classroom link ────────────────────────────────────────────────────────

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        ondelete='restrict',
        tracking=True,
        index=True,
    )

    # ── Curriculum / subject ──────────────────────────────────────────────────

    curriculum_line_id = fields.Many2one(
        comodel_name='edu.curriculum.line',
        string='Curriculum Line',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        related='curriculum_line_id.subject_id',
        store=True,
        index=True,
    )

    # ── People / placement ────────────────────────────────────────────────────

    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
        ondelete='set null',
        tracking=True,
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        related='section_id.batch_id',
        store=True,
        index=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        related='exam_session_id.academic_year_id',
        store=True,
        index=True,
    )

    # ── Schedule ──────────────────────────────────────────────────────────────

    exam_date = fields.Date(
        string='Exam Date',
        tracking=True,
    )
    time_from = fields.Float(
        string='Start Time',
        help='Start time as decimal (e.g. 9.5 = 09:30).',
    )
    time_to = fields.Float(
        string='End Time',
        help='End time as decimal (e.g. 11.0 = 11:00).',
    )
    room = fields.Char(
        string='Exam Room',
    )

    # ── Marks configuration ───────────────────────────────────────────────────

    max_marks = fields.Float(
        string='Max Marks',
        required=True,
        default=100.0,
        tracking=True,
    )
    pass_marks = fields.Float(
        string='Pass Marks',
        required=True,
        default=40.0,
        tracking=True,
    )
    weightage_percent = fields.Float(
        string='Weightage (%)',
        default=100.0,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('marks_entry', 'Marks Entry'),
            ('submitted', 'Submitted'),
            ('published', 'Published'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    note = fields.Text(
        string='Notes',
    )

    # ── Children ──────────────────────────────────────────────────────────────

    component_ids = fields.One2many(
        comodel_name='edu.exam.paper.component',
        inverse_name='exam_paper_id',
        string='Paper Components',
    )
    marksheet_ids = fields.One2many(
        comodel_name='edu.exam.marksheet',
        inverse_name='exam_paper_id',
        string='Marksheets',
    )

    # ── Computed counts ───────────────────────────────────────────────────────

    marksheet_count = fields.Integer(
        string='Marksheets',
        compute='_compute_marksheet_count',
        store=False,
    )
    component_count = fields.Integer(
        string='Components',
        compute='_compute_component_count',
        store=False,
    )

    # ── Company ───────────────────────────────────────────────────────────────

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='exam_session_id.company_id',
        store=True,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_session_curriculum_section',
            'UNIQUE(exam_session_id, curriculum_line_id, section_id)',
            'A paper for this subject and section already exists in this exam session.',
        ),
        (
            'check_max_marks_positive',
            'CHECK(max_marks > 0)',
            'Max marks must be greater than zero.',
        ),
        (
            'check_pass_le_max',
            'CHECK(pass_marks <= max_marks)',
            'Pass marks cannot exceed max marks.',
        ),
    ]

    # ── ORM ───────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('subject_id', 'section_id', 'exam_session_id')
    def _compute_display_name(self):
        for rec in self:
            parts = filter(None, [
                rec.subject_id.name,
                rec.section_id.name,
                rec.exam_session_id.name,
            ])
            rec.display_name = ' / '.join(parts) or 'New Paper'

    def _compute_marksheet_count(self):
        groups = self.env['edu.exam.marksheet']._read_group(
            domain=[('exam_paper_id', 'in', self.ids)],
            groupby=['exam_paper_id'],
            aggregates=['__count'],
        )
        counts = {paper.id: cnt for paper, cnt in groups}
        for rec in self:
            rec.marksheet_count = counts.get(rec.id, 0)

    def _compute_component_count(self):
        groups = self.env['edu.exam.paper.component']._read_group(
            domain=[('exam_paper_id', 'in', self.ids)],
            groupby=['exam_paper_id'],
            aggregates=['__count'],
        )
        counts = {paper.id: cnt for paper, cnt in groups}
        for rec in self:
            rec.component_count = counts.get(rec.id, 0)

    # ── Onchange — classroom auto-populate ────────────────────────────────────

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        if self.classroom_id:
            self.section_id = self.classroom_id.section_id
            self.program_term_id = self.classroom_id.program_term_id
            if not self.curriculum_line_id:
                self.curriculum_line_id = self.classroom_id.curriculum_line_id
            if not self.teacher_id:
                self.teacher_id = self.classroom_id.teacher_id

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('classroom_id', 'section_id', 'exam_session_id')
    def _check_classroom_context_match(self):
        for rec in self:
            if not rec.classroom_id:
                continue
            session = rec.exam_session_id
            cl = rec.classroom_id
            if session.batch_id and cl.batch_id and session.batch_id != cl.batch_id:
                raise ValidationError(
                    _(
                        'Classroom "%s" batch "%s" does not match session batch "%s".'
                    ) % (cl.name, cl.batch_id.name, session.batch_id.name)
                )
            if session.program_term_id and cl.program_term_id and session.program_term_id != cl.program_term_id:
                raise ValidationError(
                    _(
                        'Classroom "%s" program term "%s" does not match session program term "%s".'
                    ) % (cl.name, cl.program_term_id.name, session.program_term_id.name)
                )
            if rec.section_id and cl.section_id and rec.section_id != cl.section_id:
                raise ValidationError(
                    _(
                        'Section "%s" on this paper does not match classroom "%s" section "%s".'
                    ) % (rec.section_id.name, cl.name, cl.section_id.name)
                )

    # ── State transitions ────────────────────────────────────────────────────

    def action_schedule(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _('Only Draft papers can be scheduled. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'scheduled'})

    def action_start(self):
        for rec in self:
            if rec.state != 'scheduled':
                raise UserError(
                    _('Only Scheduled papers can be started. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'in_progress'})

    def action_open_marks_entry(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(
                    _('Only In Progress papers can be opened for marks entry. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'marks_entry'})

    def action_submit(self):
        for rec in self:
            if rec.state != 'marks_entry':
                raise UserError(
                    _('Only papers in Marks Entry state can be submitted. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'submitted'})

    def action_publish(self):
        is_manager = (
            self.env.user.has_group('edu_exam.group_exam_publish_manager')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_manager:
            raise UserError(
                _('Only Exam Publish Managers or Education Admins can publish papers.')
            )
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(
                    _('Only Submitted papers can be published. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'published'})

    def action_close(self):
        for rec in self:
            if rec.state != 'published':
                raise UserError(
                    _('Only Published papers can be closed. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'closed'})

    def action_reset_to_draft(self):
        is_admin = self.env.user.has_group('edu_exam.group_exam_admin') or \
                   self.env.user.has_group('edu_academic_structure.group_education_admin')
        if not is_admin:
            raise UserError(_('Only Exam Admins can reset papers to draft.'))
        for rec in self:
            if rec.state not in ('submitted', 'scheduled'):
                raise UserError(
                    _('Only Submitted or Scheduled papers can be reset to Draft. "%s" is in state: %s.')
                    % (rec.display_name, rec.state)
                )
            rec.write({'state': 'draft'})

    # ── Smart button ─────────────────────────────────────────────────────────

    def action_view_marksheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marksheets — %s') % self.display_name,
            'res_model': 'edu.exam.marksheet',
            'view_mode': 'list,form',
            'domain': [('exam_paper_id', '=', self.id)],
            'context': {
                'default_exam_paper_id': self.id,
                'default_exam_session_id': self.exam_session_id.id,
            },
        }
