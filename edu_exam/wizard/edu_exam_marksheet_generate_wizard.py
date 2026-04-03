import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduExamMarksheetGenerateWizard(models.TransientModel):
    """Wizard — generate edu.exam.marksheet records for an exam session.

    For each paper in scope, queries edu.student.progression.history for
    ALL students with state='active' in the paper's batch (across all sections),
    then creates marksheets for students that don't already have one for that
    paper / attempt_type / attempt_no combination.

    Optionally snapshots attendance percentage from each student's own
    classroom (their section × curriculum line) at generation time.
    """

    _name = 'edu.exam.marksheet.generate.wizard'
    _description = 'Generate Exam Marksheets Wizard'

    exam_session_id = fields.Many2one(
        comodel_name='edu.exam.session',
        string='Exam Session',
        required=True,
    )
    paper_ids = fields.Many2many(
        comodel_name='edu.exam.paper',
        relation='exam_ms_gen_wiz_paper_rel',
        column1='wizard_id',
        column2='paper_id',
        string='Papers',
        domain="[('exam_session_id', '=', exam_session_id)]",
        help='Leave empty to generate for all papers in the session.',
    )
    attempt_type = fields.Selection(
        selection=[
            ('regular', 'Regular'),
            ('back', 'Back'),
            ('makeup', 'Makeup'),
            ('improvement', 'Improvement'),
            ('special', 'Special'),
        ],
        string='Attempt Type',
        required=True,
        default='regular',
    )
    attempt_no = fields.Integer(
        string='Attempt No.',
        default=1,
    )
    snapshot_attendance = fields.Boolean(
        string='Snapshot Attendance',
        default=True,
        help='Fetch attendance percentage from the attendance register at generation time.',
    )
    result_message = fields.Char(
        string='Result',
        readonly=True,
    )

    def action_generate(self):
        """Generate marksheets for all active students in each paper's batch."""
        self.ensure_one()
        session = self.exam_session_id

        # Determine papers to process
        if self.paper_ids:
            papers = self.paper_ids
        else:
            papers = self.env['edu.exam.paper'].search([
                ('exam_session_id', '=', session.id),
            ])

        if not papers:
            raise UserError(_('No exam papers found for the selected session.'))

        # Build attendance cache keyed by (section_id, curriculum_line_id)
        # Each student's attendance comes from their own section's classroom
        # for that specific subject.
        attendance_cache = {}  # (section_id, curriculum_line_id) -> {student_id: {percent, ...}}
        if self.snapshot_attendance and 'edu.attendance.register' in self.env:
            batch_ids = papers.mapped('batch_id').ids
            curriculum_line_ids = papers.mapped('curriculum_line_id').ids
            if batch_ids and curriculum_line_ids:
                classrooms = self.env['edu.classroom'].search([
                    ('batch_id', 'in', batch_ids),
                    ('curriculum_line_id', 'in', curriculum_line_ids),
                ])
                classroom_ids = classrooms.ids
                registers = self.env['edu.attendance.register'].search([
                    ('classroom_id', 'in', classroom_ids),
                ])
                for reg in registers:
                    cl = reg.classroom_id
                    key = (cl.section_id.id, cl.curriculum_line_id.id)
                    attendance_cache[key] = reg.get_student_attendance_summary()

        vals_list = []
        skipped = 0
        created = 0

        for paper in papers:
            if not paper.batch_id:
                continue

            # Fetch active students in the batch who are taking this subject.
            # Students with no elected subjects set are treated as taking all subjects
            # (backwards compatibility for records created before electives were introduced).
            all_histories = self.env['edu.student.progression.history'].search([
                ('batch_id', '=', paper.batch_id.id),
                ('state', '=', 'active'),
            ])
            histories = all_histories.filtered(
                lambda h: not h.effective_curriculum_line_ids
                or paper.curriculum_line_id in h.effective_curriculum_line_ids
            )

            # Build set of already-existing student ids for this paper
            existing_records = self.env['edu.exam.marksheet'].search_read(
                domain=[
                    ('exam_paper_id', '=', paper.id),
                    ('attempt_type', '=', self.attempt_type),
                    ('attempt_no', '=', self.attempt_no),
                ],
                fields=['student_id'],
            )
            existing_student_ids = {r['student_id'][0] for r in existing_records}

            for history in histories:
                student = history.student_id
                if student.id in existing_student_ids:
                    skipped += 1
                    continue

                # Look up attendance from the student's own classroom for this subject
                att_pct = 0.0
                att_eligible = True
                if self.snapshot_attendance:
                    key = (history.section_id.id, paper.curriculum_line_id.id)
                    att_summary = attendance_cache.get(key, {})
                    if att_summary:
                        student_att = att_summary.get(student.id)
                        if student_att:
                            att_pct = student_att.get('percent', 0.0)
                        else:
                            att_eligible = False

                vals_list.append({
                    'exam_paper_id': paper.id,
                    'student_id': student.id,
                    'enrollment_id': history.enrollment_id.id if history.enrollment_id else False,
                    'student_progression_history_id': history.id,
                    'batch_id': history.batch_id.id if history.batch_id else False,
                    'section_id': history.section_id.id if history.section_id else False,
                    'program_term_id': history.program_term_id.id if history.program_term_id else False,
                    'subject_id': paper.subject_id.id if paper.subject_id else False,
                    'curriculum_line_id': paper.curriculum_line_id.id,
                    'academic_year_id': session.academic_year_id.id if session.academic_year_id else False,
                    'attempt_type': self.attempt_type,
                    'attempt_no': self.attempt_no,
                    'status': 'present',
                    'raw_marks': 0.0,
                    'grace_marks': 0.0,
                    'is_latest_attempt': True,
                    'entered_by': self.env.user.id,
                    'attendance_percent_snapshot': att_pct,
                    'attendance_eligible': att_eligible,
                })

        if vals_list:
            self.env['edu.exam.marksheet'].create(vals_list)
            created = len(vals_list)

        msg = _('Done. Created: %d marksheets. Skipped (already exist): %d.') % (created, skipped)
        self.result_message = msg

        # Return the same wizard form with the result message
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
