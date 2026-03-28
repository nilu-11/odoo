import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduBackExamGenerationWizard(models.TransientModel):
    """Wizard — create a back/makeup/improvement/special exam session with
    marksheets for selected student-subject candidates.

    Two modes:
    - create_new_session: create a new edu.exam.session with the given dates
      and attempt_type, then populate papers and marksheets.
    - use_existing_session: attach new papers/marksheets to an already-existing
      back exam session.

    Marksheet attempt tracking:
    - previous_marksheet_id on the new marksheet points to the failed attempt.
    - The previous marksheet's is_latest_attempt is set to False.
    - The new marksheet's is_latest_attempt is True.
    """

    _name = 'edu.back.exam.generation.wizard'
    _description = 'Back Exam Generation Wizard'

    name = fields.Char(
        string='Session Name',
        help='Name for the new back exam session (used when mode=create_new_session).',
    )
    mode = fields.Selection(
        selection=[
            ('create_new_session', 'Create New Session'),
            ('use_existing_session', 'Use Existing Session'),
        ],
        string='Mode',
        default='create_new_session',
        required=True,
    )
    existing_exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Existing Session',
        domain=[('attempt_type', 'in', ('back', 'makeup', 'improvement', 'special'))],
        help='Used when mode=use_existing_session.',
    )
    based_on_exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Based on Exam Session',
        help='The original exam session whose failures are being addressed.',
    )
    based_on_result_session_id = fields.Many2one(
        comodel_name='edu.result.session',
        string='Based on Result Session',
        help='The result session that flagged the backlogs (optional).',
    )
    back_exam_policy_id = fields.Many2one(
        comodel_name='edu.back.exam.policy',
        string='Back Exam Policy',
    )
    attempt_type = fields.Selection(
        selection=[
            ('back', 'Back'),
            ('makeup', 'Makeup'),
            ('improvement', 'Improvement'),
            ('special', 'Special'),
        ],
        string='Attempt Type',
        required=True,
        default='back',
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
    )
    candidate_line_ids = fields.One2many(
        comodel_name='edu.back.exam.candidate.line',
        inverse_name='wizard_id',
        string='Candidates',
    )
    result_summary = fields.Char(
        string='Result',
        readonly=True,
    )

    def action_generate(self):
        """Create (or use existing) exam session and populate papers + marksheets."""
        self.ensure_one()

        if self.date_end < self.date_start:
            raise UserError(_('End Date cannot be earlier than Start Date.'))

        candidates = self.candidate_line_ids.filtered(lambda l: l.include)
        if not candidates:
            raise UserError(_('No candidates selected. Please mark at least one candidate to include.'))

        # ── 1. Resolve target session ────────────────────────────────────────
        if self.mode == 'create_new_session':
            session_name = self.name or (
                _('%s Exam %s') % (
                    dict(self._fields['attempt_type'].selection).get(self.attempt_type, self.attempt_type),
                    self.academic_year_id.name or '',
                )
            )
            session = self.env['edu.exam.session'].create({
                'name': session_name,
                'academic_year_id': self.academic_year_id.id,
                'attempt_type': self.attempt_type,
                'exam_type': 'internal',
                'exam_scope': 'batch',
                'based_on_exam_session_id': self.based_on_exam_session_id.id if self.based_on_exam_session_id else False,
                'based_on_result_session_id': self.based_on_result_session_id.id if self.based_on_result_session_id else False,
                'back_exam_policy_id': self.back_exam_policy_id.id if self.back_exam_policy_id else False,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'state': 'draft',
            })
        else:
            session = self.existing_exam_session_id
            if not session:
                raise UserError(_('Please select an existing exam session.'))

        # ── 2. Process each candidate ─────────────────────────────────────────
        created_papers = 0
        created_marksheets = 0

        for line in candidates:
            # Find or create paper for (session, curriculum_line, section)
            paper = self.env['edu.exam.paper'].search([
                ('exam_session_id', '=', session.id),
                ('curriculum_line_id', '=', line.curriculum_line_id.id),
                ('section_id', '=', line.section_id.id if line.section_id else False),
            ], limit=1)

            if not paper:
                paper_vals = {
                    'exam_session_id': session.id,
                    'curriculum_line_id': line.curriculum_line_id.id,
                    'section_id': line.section_id.id if line.section_id else False,
                    'program_term_id': (
                        line.student_progression_history_id.program_term_id.id
                        if line.student_progression_history_id
                        else False
                    ),
                    'max_marks': (
                        line.previous_marksheet_id.max_marks
                        if line.previous_marksheet_id else 100.0
                    ),
                    'pass_marks': (
                        line.previous_marksheet_id.pass_marks
                        if line.previous_marksheet_id else 40.0
                    ),
                    'state': 'draft',
                }
                paper = self.env['edu.exam.paper'].create(paper_vals)
                created_papers += 1

            # Check if marksheet already exists
            existing_ms = self.env['edu.exam.marksheet'].search([
                ('exam_paper_id', '=', paper.id),
                ('student_id', '=', line.student_id.id),
                ('attempt_type', '=', self.attempt_type),
                ('attempt_no', '=', line.attempt_no),
            ], limit=1)

            if existing_ms:
                continue

            # Mark previous attempt as not latest
            if line.previous_marksheet_id:
                line.previous_marksheet_id.write({'is_latest_attempt': False})

            # Build snapshot from progression history
            history = line.student_progression_history_id
            ms_vals = {
                'exam_paper_id': paper.id,
                'student_id': line.student_id.id,
                'enrollment_id': history.enrollment_id.id if history and history.enrollment_id else False,
                'student_progression_history_id': history.id if history else False,
                'batch_id': history.batch_id.id if history and history.batch_id else False,
                'section_id': history.section_id.id if history and history.section_id else False,
                'program_term_id': history.program_term_id.id if history and history.program_term_id else False,
                'subject_id': line.curriculum_line_id.subject_id.id if line.curriculum_line_id else False,
                'curriculum_line_id': line.curriculum_line_id.id,
                'academic_year_id': session.academic_year_id.id if session.academic_year_id else False,
                'attempt_type': self.attempt_type,
                'attempt_no': line.attempt_no,
                'status': 'present',
                'raw_marks': 0.0,
                'grace_marks': 0.0,
                'is_latest_attempt': True,
                'previous_marksheet_id': line.previous_marksheet_id.id if line.previous_marksheet_id else False,
                'backlog_origin_result_id': (
                    line.previous_marksheet_id.backlog_origin_result_id.id
                    if line.previous_marksheet_id and line.previous_marksheet_id.backlog_origin_result_id
                    else False
                ),
                'entered_by': self.env.user.id,
            }
            self.env['edu.exam.marksheet'].create(ms_vals)
            created_marksheets += 1

        self.result_summary = _(
            'Done. Session: "%s". Papers created: %d. Marksheets created: %d.'
        ) % (session.name, created_papers, created_marksheets)

        # Return action to view the session
        return {
            'type': 'ir.actions.act_window',
            'name': _('Back Exam Session'),
            'res_model': 'edu.exam.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
        }


class EduBackExamCandidateLine(models.TransientModel):
    """Candidate line — one student × subject for a back exam."""

    _name = 'edu.back.exam.candidate.line'
    _description = 'Back Exam Candidate Line'
    _order = 'student_id, curriculum_line_id'

    wizard_id = fields.Many2one(
        comodel_name='edu.back.exam.generation.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        required=True,
    )
    student_progression_history_id = fields.Many2one(
        comodel_name='edu.student.progression.history',
        string='Progression History',
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='edu.curriculum.line',
        string='Curriculum Line',
        required=True,
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        related='curriculum_line_id.subject_id',
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
    )
    previous_marksheet_id = fields.Many2one(
        comodel_name='edu.exam.marksheet',
        string='Previous Attempt',
        help='The failed/previous marksheet that qualifies this student for a back exam.',
    )
    attempt_no = fields.Integer(
        string='Attempt No.',
        default=1,
    )
    include = fields.Boolean(
        string='Include',
        default=True,
    )
