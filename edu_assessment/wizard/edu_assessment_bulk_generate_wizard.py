import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduAssessmentBulkGenerateWizard(models.TransientModel):
    """Wizard — bulk-generate draft continuous assessment records for all
    active students in a classroom.

    The teacher selects:
    - classroom (provides section, program_term, subject context)
    - assessment category
    - assessment title / date / max_marks

    The system then creates one draft record per active student in the
    classroom's section (from edu.student.progression.history), skipping
    students who already have a record for the same title+category+date
    (when avoid_duplicates is enabled).
    """

    _name = 'edu.assessment.bulk.generate.wizard'
    _description = 'Bulk Generate Assessment Records Wizard'

    # ── Core input ────────────────────────────────────────────────────────────

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        required=True,
    )
    category_id = fields.Many2one(
        comodel_name='edu.assessment.category',
        string='Assessment Category',
        required=True,
    )
    assessment_name = fields.Char(
        string='Assessment Title',
        required=True,
        help='Descriptive title, e.g. "Assignment 1", "Class Test 2".',
    )
    assessment_date = fields.Date(
        string='Assessment Date',
        required=True,
        default=fields.Date.today,
    )
    max_marks = fields.Float(
        string='Max Marks',
        required=True,
        default=100.0,
    )
    teacher_id = fields.Many2one(
        comodel_name='res.users',
        string='Teacher',
        default=lambda self: self.env.user,
    )

    # ── Options ───────────────────────────────────────────────────────────────

    avoid_duplicates = fields.Boolean(
        string='Skip Existing',
        default=True,
        help='Skip students who already have a record with the same '
             'category, title, and date in this classroom.',
    )

    # ── Derived context (readonly display) ───────────────────────────────────

    section_id = fields.Many2one(
        comodel_name='edu.section',
        string='Section',
        related='classroom_id.section_id',
    )
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        related='classroom_id.subject_id',
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Program Term',
        related='classroom_id.program_term_id',
    )

    # ── Result ────────────────────────────────────────────────────────────────

    result_message = fields.Char(
        string='Result',
        readonly=True,
    )

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id and self.category_id.default_max_marks:
            self.max_marks = self.category_id.default_max_marks

    @api.onchange('classroom_id')
    def _onchange_classroom_id(self):
        if self.classroom_id and self.classroom_id.teacher_id:
            if self.teacher_id == self.env.user:
                self.teacher_id = self.classroom_id.teacher_id

    # ── Generate action ───────────────────────────────────────────────────────

    def action_generate(self):
        """Create draft assessment records for all active students."""
        self.ensure_one()
        classroom = self.classroom_id
        if not classroom.section_id:
            raise UserError(
                _('Classroom "%s" has no section assigned.') % classroom.name
            )

        # Fetch active progression histories for the classroom's section,
        # filtered by elective subject choices.  Students with no elected
        # subjects set are treated as taking all subjects (backwards compat).
        curriculum_line = classroom.curriculum_line_id
        all_histories = self.env['edu.student.progression.history'].search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        histories = all_histories.filtered(
            lambda h: not h.effective_curriculum_line_ids
            or curriculum_line in h.effective_curriculum_line_ids
        )
        if not histories:
            raise UserError(
                _(
                    'No active students found in section "%s". '
                    'Make sure progression histories are active.'
                ) % classroom.section_id.name
            )

        # Build set of existing (student_id, category_id, name, date) tuples
        existing_key_set = set()
        if self.avoid_duplicates:
            existing = self.env['edu.continuous.assessment.record'].search_read(
                domain=[
                    ('classroom_id', '=', classroom.id),
                    ('category_id', '=', self.category_id.id),
                    ('name', '=', self.assessment_name),
                    ('assessment_date', '=', self.assessment_date),
                ],
                fields=['student_id'],
            )
            existing_key_set = {r['student_id'][0] for r in existing}

        # Derive academic_year from program_term if available
        academic_year_id = False
        if classroom.program_term_id and hasattr(classroom.program_term_id, 'academic_year_id'):
            academic_year_id = classroom.program_term_id.academic_year_id.id

        vals_list = []
        skipped = 0
        for history in histories:
            student = history.student_id
            if self.avoid_duplicates and student.id in existing_key_set:
                skipped += 1
                continue

            vals_list.append({
                'name': self.assessment_name,
                'category_id': self.category_id.id,
                'student_id': student.id,
                'enrollment_id': history.enrollment_id.id if history.enrollment_id else False,
                'student_progression_history_id': history.id,
                'classroom_id': classroom.id,
                'subject_id': classroom.subject_id.id if classroom.subject_id else False,
                'curriculum_line_id': classroom.curriculum_line_id.id if classroom.curriculum_line_id else False,
                'batch_id': history.batch_id.id if history.batch_id else False,
                'section_id': history.section_id.id if history.section_id else False,
                'program_term_id': history.program_term_id.id if history.program_term_id else False,
                'academic_year_id': academic_year_id or (
                    history.academic_year_id.id if history.academic_year_id else False
                ),
                'teacher_id': self.teacher_id.id if self.teacher_id else self.env.user.id,
                'assessment_date': self.assessment_date,
                'max_marks': self.max_marks,
                'marks_obtained': 0.0,
                'state': 'draft',
            })

        created_count = 0
        if vals_list:
            created = self.env['edu.continuous.assessment.record'].create(vals_list)
            created_count = len(created)

        msg = _(
            'Done. Created: %d assessment records. Skipped (already exist): %d.'
        ) % (created_count, skipped)
        self.result_message = msg

        if not created_count:
            # Return same wizard to show message
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        # Open the created records
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assessment Records — %s') % self.assessment_name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [
                ('classroom_id', '=', classroom.id),
                ('category_id', '=', self.category_id.id),
                ('name', '=', self.assessment_name),
                ('assessment_date', '=', self.assessment_date),
            ],
            'context': {'default_classroom_id': classroom.id},
            'target': 'current',
        }
