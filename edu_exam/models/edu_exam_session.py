import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .edu_assessment_scheme import EXAM_TYPE_SELECTION, ATTEMPT_TYPE_SELECTION

_logger = logging.getLogger(__name__)


class EduExamSession(models.Model):
    """Exam Session — the top-level container for a set of exam papers.

    A session scopes one examination event (e.g. "Semester 1 Internal 2025")
    across a batch, program term, or specific sections.  Individual subject
    papers are children (edu.exam.paper) of the session.

    Workflow: draft → planned → ongoing → marks_entry → published → closed
    """

    _name = 'edu.exam.session'
    _description = 'Exam Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, name'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Session Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Code',
        tracking=True,
        copy=False,
        help='Auto-generated from sequence if left blank on create.',
    )

    # ── Assessment scheme ─────────────────────────────────────────────────────

    assessment_scheme_id = fields.Many2one(
        comodel_name='edu.assessment.scheme',
        string='Assessment Scheme',
        ondelete='set null',
        tracking=True,
    )
    assessment_scheme_line_id = fields.Many2one(
        comodel_name='edu.assessment.scheme.line',
        string='Scheme Component',
        domain="[('scheme_id', '=', assessment_scheme_id)]",
        ondelete='set null',
        tracking=True,
    )

    # ── Exam classification ───────────────────────────────────────────────────

    exam_scope = fields.Selection(
        selection=[
            ('institution', 'Institution-wide'),
            ('program', 'Program'),
            ('batch', 'Batch'),
            ('section', 'Section'),
            ('classroom', 'Classroom'),
            ('program_term', 'Program Term'),
        ],
        string='Exam Scope',
        required=True,
        default='batch',
        tracking=True,
    )
    exam_type = fields.Selection(
        selection=EXAM_TYPE_SELECTION,
        string='Exam Type',
        required=True,
        default='internal',
        tracking=True,
        index=True,
    )
    attempt_type = fields.Selection(
        selection=ATTEMPT_TYPE_SELECTION,
        string='Attempt Type',
        required=True,
        default='regular',
        tracking=True,
        index=True,
    )
    is_board_exam = fields.Boolean(
        string='Board Exam',
        tracking=True,
    )
    is_external_exam = fields.Boolean(
        string='External Exam',
        tracking=True,
    )

    # ── Academic scope ────────────────────────────────────────────────────────

    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    section_ids = fields.Many2many(
        comodel_name='edu.section',
        relation='edu_exam_session_section_rel',
        column1='session_id',
        column2='section_id',
        string='Sections',
    )

    # ── Back exam references ──────────────────────────────────────────────────

    based_on_result_session_id = fields.Many2one(
        comodel_name='edu.result.session',
        string='Based on Result Session',
        ondelete='set null',
        tracking=True,
        help='For back/makeup exams: the result session whose failures this session addresses.',
    )
    based_on_exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Based on Exam Session',
        ondelete='set null',
        tracking=True,
        help='For back/makeup exams: the original exam session being retaken.',
    )
    back_exam_policy_id = fields.Many2one(
        comodel_name='edu.back.exam.policy',
        string='Back Exam Policy',
        ondelete='set null',
        tracking=True,
    )

    # ── Schedule ──────────────────────────────────────────────────────────────

    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('planned', 'Planned'),
            ('ongoing', 'Ongoing'),
            ('marks_entry', 'Marks Entry'),
            ('published', 'Published'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Other ─────────────────────────────────────────────────────────────────

    note = fields.Text(
        string='Notes',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        store=True,
        index=True,
    )

    # ── Computed counts ───────────────────────────────────────────────────────

    paper_count = fields.Integer(
        string='Papers',
        compute='_compute_paper_count',
        store=False,
    )
    marksheet_count = fields.Integer(
        string='Marksheets',
        compute='_compute_marksheet_count',
        store=False,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────

    _sql_constraints = [
        (
            'unique_code_company',
            'UNIQUE(code, company_id)',
            'Exam Session code must be unique per company.',
        ),
    ]

    # ── ORM overrides ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = seq.next_by_code('edu.exam.session.code') or '/'
        return super().create(vals_list)

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(
                    _('End Date cannot be earlier than Start Date on session "%s".') % rec.name
                )

    @api.constrains('batch_id', 'program_id')
    def _check_batch_program(self):
        for rec in self:
            if rec.batch_id and rec.program_id:
                if rec.batch_id.program_id != rec.program_id:
                    raise ValidationError(
                        _(
                            'Batch "%s" does not belong to Program "%s".'
                        ) % (rec.batch_id.name, rec.program_id.name)
                    )

    @api.constrains('program_term_id', 'program_id')
    def _check_program_term_program(self):
        for rec in self:
            if rec.program_term_id and rec.program_id:
                if rec.program_term_id.program_id != rec.program_id:
                    raise ValidationError(
                        _(
                            'Program Term "%s" does not belong to Program "%s".'
                        ) % (rec.program_term_id.name, rec.program_id.name)
                    )

    @api.constrains('section_ids', 'batch_id')
    def _check_sections_batch(self):
        for rec in self:
            if rec.batch_id and rec.section_ids:
                invalid = rec.section_ids.filtered(
                    lambda s: s.batch_id != rec.batch_id
                )
                if invalid:
                    raise ValidationError(
                        _(
                            'Sections %s do not belong to Batch "%s".'
                        ) % (
                            ', '.join(invalid.mapped('name')),
                            rec.batch_id.name,
                        )
                    )

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id:
            self.program_id = self.batch_id.program_id
            self.section_ids = [(5, 0, 0)]
        else:
            self.program_id = False
            self.section_ids = [(5, 0, 0)]

    @api.onchange('program_id')
    def _onchange_program_id(self):
        if self.batch_id and self.program_id:
            if self.batch_id.program_id != self.program_id:
                self.batch_id = False
                self.section_ids = [(5, 0, 0)]

    @api.onchange('assessment_scheme_id')
    def _onchange_assessment_scheme_id(self):
        if not self.assessment_scheme_id:
            self.assessment_scheme_line_id = False
        elif (
            self.assessment_scheme_line_id
            and self.assessment_scheme_line_id.scheme_id != self.assessment_scheme_id
        ):
            self.assessment_scheme_line_id = False

    # ── Computed ─────────────────────────────────────────────────────────────

    def _compute_paper_count(self):
        groups = self.env['edu.exam.paper']._read_group(
            domain=[('exam_session_id', 'in', self.ids)],
            groupby=['exam_session_id'],
            aggregates=['__count'],
        )
        counts = {session.id: cnt for session, cnt in groups}
        for rec in self:
            rec.paper_count = counts.get(rec.id, 0)

    def _compute_marksheet_count(self):
        groups = self.env['edu.exam.marksheet']._read_group(
            domain=[('exam_session_id', 'in', self.ids)],
            groupby=['exam_session_id'],
            aggregates=['__count'],
        )
        counts = {session.id: cnt for session, cnt in groups}
        for rec in self:
            rec.marksheet_count = counts.get(rec.id, 0)

    # ── State transitions ────────────────────────────────────────────────────

    def action_plan(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _('Only Draft sessions can be planned. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'planned'})

    def action_start(self):
        for rec in self:
            if rec.state != 'planned':
                raise UserError(
                    _('Only Planned sessions can be started. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'ongoing'})

    def action_open_marks_entry(self):
        for rec in self:
            if rec.state != 'ongoing':
                raise UserError(
                    _('Only Ongoing sessions can be opened for marks entry. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'marks_entry'})

    def action_publish(self):
        """Publish — restricted to group_exam_publish_manager or education admin."""
        is_manager = (
            self.env.user.has_group('edu_exam.group_exam_publish_manager')
            or self.env.user.has_group('edu_academic_structure.group_education_admin')
        )
        if not is_manager:
            raise UserError(
                _('Only Exam Publish Managers or Education Admins can publish exam sessions.')
            )
        for rec in self:
            if rec.state != 'marks_entry':
                raise UserError(
                    _('Only sessions in Marks Entry state can be published. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'published'})

    def action_close(self):
        for rec in self:
            if rec.state != 'published':
                raise UserError(
                    _('Only Published sessions can be closed. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'closed'})

    def action_cancel(self):
        for rec in self:
            if rec.state == 'closed':
                raise UserError(
                    _('Closed session "%s" cannot be cancelled.') % rec.name
                )
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    _('Only Cancelled sessions can be reset to Draft. "%s" is in state: %s.')
                    % (rec.name, rec.state)
                )
            rec.write({'state': 'draft'})

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Papers — %s') % self.name,
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': [('exam_session_id', '=', self.id)],
            'context': {
                'default_exam_session_id': self.id,
                'default_academic_year_id': self.academic_year_id.id,
            },
        }

    def action_view_marksheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marksheets — %s') % self.name,
            'res_model': 'edu.exam.marksheet',
            'view_mode': 'list,form',
            'domain': [('exam_session_id', '=', self.id)],
            'context': {
                'default_exam_session_id': self.id,
            },
        }

    def action_generate_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Exam Papers'),
            'res_model': 'edu.exam.paper.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_exam_session_id': self.id,
            },
        }
