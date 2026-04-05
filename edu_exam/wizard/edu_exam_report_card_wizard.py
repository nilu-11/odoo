from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduExamReportCardWizard(models.TransientModel):
    """Wizard to print student-wise exam report cards for an exam session."""

    _name = 'edu.exam.report.card.wizard'
    _description = 'Exam Report Card Wizard'

    exam_session_id = fields.Many2one(
        'edu.exam.session', string='Exam Session',
        required=True,
        domain="[('state', 'in', ('marks_entry', 'published', 'closed'))]",
    )
    student_ids = fields.Many2many(
        'edu.student', string='Students',
        help='Leave empty to print report cards for all students in the session.',
    )
    batch_id = fields.Many2one(
        'edu.batch', string='Batch',
        related='exam_session_id.batch_id', readonly=True,
    )
    academic_year_id = fields.Many2one(
        'edu.academic.year', string='Academic Year',
        related='exam_session_id.academic_year_id', readonly=True,
    )
    include_absent = fields.Boolean(
        string='Include Absent Subjects',
        default=True,
        help='Include subjects where the student was absent.',
    )
    include_components = fields.Boolean(
        string='Show Component Breakdown',
        default=False,
        help='Show marks for individual components (Theory, Practical, etc.).',
    )

    @api.onchange('exam_session_id')
    def _onchange_exam_session_id(self):
        if self.exam_session_id:
            self.student_ids = [(5, 0, 0)]

    def _get_report_data(self):
        """Build structured data for the report template."""
        self.ensure_one()
        session = self.exam_session_id

        # Base domain: latest attempts in this session
        domain = [
            ('exam_session_id', '=', session.id),
            ('is_latest_attempt', '=', True),
        ]
        if self.student_ids:
            domain.append(('student_id', 'in', self.student_ids.ids))
        if not self.include_absent:
            domain.append(('status', '!=', 'absent'))

        marksheets = self.env['edu.exam.marksheet'].search(
            domain, order='student_id, subject_id'
        )
        if not marksheets:
            raise UserError(
                _('No marksheets found for the selected session and students.')
            )

        # Group marksheets by student
        students_data = []
        current_student = None
        current_marks = []

        for ms in marksheets:
            if current_student != ms.student_id:
                if current_student and current_marks:
                    students_data.append(
                        self._build_student_data(current_student, current_marks)
                    )
                current_student = ms.student_id
                current_marks = []
            current_marks.append(ms)

        # Don't forget the last student
        if current_student and current_marks:
            students_data.append(
                self._build_student_data(current_student, current_marks)
            )

        return {
            'session': session,
            'students_data': students_data,
            'include_components': self.include_components,
            'company': self.env.company,
        }

    def _build_student_data(self, student, marksheets):
        """Build data dict for one student's report card."""
        first_ms = marksheets[0]

        total_max = 0.0
        total_obtained = 0.0
        total_pass = 0.0
        subjects_passed = 0
        subjects_failed = 0
        subjects_absent = 0

        subjects = []
        for ms in marksheets:
            subject_data = {
                'name': ms.subject_id.name or '',
                'max_marks': ms.max_marks,
                'pass_marks': ms.pass_marks,
                'raw_marks': ms.raw_marks,
                'grace_marks': ms.grace_marks,
                'final_marks': ms.final_marks,
                'status': ms.status,
                'is_pass': ms.is_pass,
                'components': [],
            }

            # Component breakdown
            if ms.component_mark_ids:
                for comp in ms.component_mark_ids:
                    subject_data['components'].append({
                        'name': comp.component_name or '',
                        'type': comp.component_type or '',
                        'max_marks': comp.max_marks,
                        'marks_obtained': comp.marks_obtained,
                        'grace_marks': comp.grace_marks,
                        'final_marks': comp.final_marks,
                        'is_pass': comp.is_pass,
                        'status': comp.status,
                    })

            subjects.append(subject_data)

            if ms.status == 'present':
                total_max += ms.max_marks
                total_obtained += ms.final_marks
                total_pass += ms.pass_marks
                if ms.is_pass:
                    subjects_passed += 1
                else:
                    subjects_failed += 1
            elif ms.status == 'absent':
                subjects_absent += 1
                total_max += ms.max_marks
                total_pass += ms.pass_marks
            elif ms.status == 'exempt':
                pass  # Don't count exempted subjects
            else:
                # withheld, malpractice
                subjects_failed += 1
                total_max += ms.max_marks
                total_pass += ms.pass_marks

        percentage = round((total_obtained / total_max) * 100, 2) if total_max else 0.0
        overall_pass = subjects_failed == 0 and subjects_absent == 0

        return {
            'student': student,
            'batch': first_ms.batch_id,
            'section': first_ms.section_id,
            'program_term': first_ms.program_term_id,
            'enrollment': first_ms.enrollment_id,
            'subjects': subjects,
            'total_max': total_max,
            'total_obtained': total_obtained,
            'total_pass': total_pass,
            'percentage': percentage,
            'subjects_passed': subjects_passed,
            'subjects_failed': subjects_failed,
            'subjects_absent': subjects_absent,
            'total_subjects': len(marksheets),
            'overall_pass': overall_pass,
        }

    def action_print(self):
        """Print the report card PDF."""
        self.ensure_one()
        # Validate
        self._get_report_data()
        return self.env.ref(
            'edu_exam.action_report_edu_exam_report_card'
        ).report_action(self)
