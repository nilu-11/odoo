import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduExamPaperGenerateWizard(models.TransientModel):
    """Wizard — generate edu.exam.paper records for an exam session.

    Two scopes are supported:
    - from_classrooms: use active classrooms matching the session's batch /
      program_term to auto-derive curriculum lines and teachers.  One paper
      per curriculum line per batch is created (batch-scoped, not per section).
    - from_curriculum: use the curriculum lines of the session's program_term
      directly (no classroom required).

    The wizard first loads a preview (action_load_preview) so the user can
    review what will be created, toggle off unwanted lines, then calls
    action_generate to do the actual creation idempotently.
    """

    _name = 'edu.exam.paper.generate.wizard'
    _description = 'Generate Exam Papers Wizard'

    exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Exam Session',
        required=True,
    )
    scope = fields.Selection(
        selection=[
            ('from_classrooms', 'From Active Classrooms'),
            ('from_curriculum', 'From Curriculum Lines'),
        ],
        string='Generation Scope',
        default='from_classrooms',
        required=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        related='exam_session_id.batch_id',
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        related='exam_session_id.program_term_id',
    )
    default_max_marks = fields.Float(
        string='Default Max Marks',
        default=100.0,
    )
    default_pass_marks = fields.Float(
        string='Default Pass Marks',
        default=40.0,
    )
    preview_line_ids = fields.One2many(
        comodel_name='edu.exam.paper.generate.wizard.line',
        inverse_name='wizard_id',
        string='Preview',
    )
    result_summary = fields.Char(
        string='Result',
        readonly=True,
    )

    def action_load_preview(self):
        """Populate preview_line_ids based on the chosen scope.

        One paper per curriculum line per batch — the whole batch sits
        together for each exam, so section is not a differentiator here.
        """
        self.ensure_one()
        session = self.exam_session_id
        if not session:
            raise UserError(_('Please select an Exam Session first.'))
        if not session.batch_id:
            raise UserError(_('The exam session must have a Batch set.'))

        batch = session.batch_id

        # Clear existing preview lines
        self.preview_line_ids.unlink()

        lines_to_create = []

        if self.scope == 'from_classrooms':
            domain = [
                ('state', '=', 'active'),
                ('batch_id', '=', batch.id),
            ]
            if session.program_term_id:
                domain.append(('program_term_id', '=', session.program_term_id.id))

            classrooms = self.env['edu.classroom'].search(domain)

            # Deduplicate: one paper per curriculum_line (batch-scoped).
            # If multiple classrooms teach the same subject (different sections),
            # pick the first teacher encountered.
            seen = {}  # curriculum_line_id -> first classroom
            for cl in classrooms:
                if cl.curriculum_line_id.id not in seen:
                    seen[cl.curriculum_line_id.id] = cl

            for curriculum_line_id, cl in seen.items():
                already = bool(self.env['edu.exam.paper'].search([
                    ('exam_session_id', '=', session.id),
                    ('curriculum_line_id', '=', curriculum_line_id),
                    ('batch_id', '=', batch.id),
                ], limit=1))
                lines_to_create.append({
                    'wizard_id': self.id,
                    'classroom_id': cl.id,
                    'curriculum_line_id': curriculum_line_id,
                    'teacher_id': cl.teacher_id.id if cl.teacher_id else False,
                    'already_exists': already,
                    'will_create': not already,
                })

        else:  # from_curriculum
            if not session.program_term_id:
                raise UserError(
                    _('The exam session must have a Program Term set to use the curriculum scope.')
                )
            curriculum_lines = self.env['edu.curriculum.line'].search([
                ('program_term_id', '=', session.program_term_id.id),
            ])
            for cl_line in curriculum_lines:
                already = bool(self.env['edu.exam.paper'].search([
                    ('exam_session_id', '=', session.id),
                    ('curriculum_line_id', '=', cl_line.id),
                    ('batch_id', '=', batch.id),
                ], limit=1))
                lines_to_create.append({
                    'wizard_id': self.id,
                    'classroom_id': False,
                    'curriculum_line_id': cl_line.id,
                    'teacher_id': False,
                    'already_exists': already,
                    'will_create': not already,
                })

        if lines_to_create:
            self.env['edu.exam.paper.generate.wizard.line'].create(lines_to_create)
        self.result_summary = _('%d lines loaded (%d already exist).') % (
            len(lines_to_create),
            sum(1 for l in lines_to_create if l.get('already_exists')),
        )

        # Return the same wizard so user can review before generating
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_generate(self):
        """Create exam papers for all preview lines where will_create=True
        and already_exists=False.  Idempotent — checks existence before create.
        """
        self.ensure_one()
        session = self.exam_session_id
        batch = session.batch_id
        created_count = 0
        skipped_count = 0
        vals_list = []

        lines = self.preview_line_ids.filtered(lambda l: l.will_create and not l.already_exists)
        for line in lines:
            # Final idempotency check
            existing = self.env['edu.exam.paper'].search([
                ('exam_session_id', '=', session.id),
                ('curriculum_line_id', '=', line.curriculum_line_id.id),
                ('batch_id', '=', batch.id),
            ], limit=1)
            if existing:
                skipped_count += 1
                continue
            vals = {
                'exam_session_id': session.id,
                'curriculum_line_id': line.curriculum_line_id.id,
                'batch_id': batch.id,
                'classroom_id': line.classroom_id.id if line.classroom_id else False,
                'teacher_id': line.teacher_id.id if line.teacher_id else False,
                'program_term_id': session.program_term_id.id if session.program_term_id else False,
                'max_marks': self.default_max_marks,
                'pass_marks': self.default_pass_marks,
                'state': 'draft',
            }
            vals_list.append(vals)

        if vals_list:
            created = self.env['edu.exam.paper'].create(vals_list)
            created_count = len(created)

        # Return action to view created papers
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Exam Papers'),
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': [('exam_session_id', '=', session.id)],
            'context': {'default_exam_session_id': session.id},
            'target': 'current',
        }


class EduExamPaperGenerateWizardLine(models.TransientModel):
    """Preview line for the paper generation wizard."""

    _name = 'edu.exam.paper.generate.wizard.line'
    _description = 'Exam Paper Generate Wizard Line'
    _order = 'curriculum_line_id'

    wizard_id = fields.Many2one(
        comodel_name='edu.exam.paper.generate.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        ondelete='set null',
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='edu.curriculum.line',
        string='Curriculum Line',
        ondelete='cascade',
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        related='curriculum_line_id.subject_id',
    )
    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
    )
    already_exists = fields.Boolean(
        string='Already Exists',
        default=False,
    )
    will_create = fields.Boolean(
        string='Create',
        default=True,
    )
