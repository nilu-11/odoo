"""Teacher in-classroom hub controllers.

Owns every ``/portal/teacher/classroom/<int:classroom_id>/<tab>`` route.
Each handler:

1. Calls ``guard_classroom_access(classroom_id, 'teacher')`` as its
   first line — returns 404 if the user doesn't own the classroom.
2. Calls ``build_portal_context(...)`` to get the shared context with
   registry-resolved sidebar items and classroom tabs.
3. Loads per-tab data and merges it in.
4. Renders the role-specific template.

The 6 built-in tabs are: stream, attendance, exams, assessments,
results, people. Tabs not yet implemented render a "coming soon"
placeholder via the shared empty_state_component.
"""
from odoo import http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_teacher_employee,
    guard_classroom_access,
)


class TeacherClassroomController(http.Controller):

    # ─── Auth plumbing ─────────────────────────────────────────

    def _guard(self, classroom_id):
        """Return (classroom, employee) or None if unauthorised."""
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        classroom = guard_classroom_access(classroom_id, 'teacher')
        if not classroom:
            return None
        employee = get_teacher_employee(user)
        return classroom, employee

    # ─── Entry point: /portal/teacher/classroom/<id> → stream ──

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_index(self, classroom_id, **kw):
        """Bare classroom URL redirects to the default tab (stream)."""
        return request.redirect(f'/portal/teacher/classroom/{classroom_id}/stream')

    # ─── Tab: Stream ───────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/stream',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_stream(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='stream',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
        })
        return request.render('edu_portal.teacher_classroom_stream_page', context)

    # ─── Tab: Attendance ───────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_attendance(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        # Today's sheet in edit mode
        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        register = classroom.attendance_register_id
        if not register:
            classroom._ensure_attendance_register()
            register = classroom.attendance_register_id
        sheet = AttendanceSheet.search([
            ('register_id', '=', register.id),
            ('state', 'in', ['draft', 'in_progress']),
        ], order='session_date desc', limit=1)
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='attendance',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'sheet': sheet,
        })
        return request.render('edu_portal.teacher_classroom_attendance_page', context)

    @http.route(
        '/portal/teacher/classroom/attendance/mark',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_attendance_mark(self, line_id, status, **kw):
        """HTMX row update — auth-checked via the line's parent classroom."""
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        line = request.env['edu.attendance.sheet.line'].sudo().browse(int(line_id))
        if not line.exists():
            return request.not_found()
        classroom = line.classroom_id
        if not guard_classroom_access(classroom.id, 'teacher'):
            return request.not_found()
        if status not in ('present', 'absent', 'late', 'excused'):
            return request.not_found()
        line.write({'status': status})
        return request.render('edu_portal.teacher_attendance_row_partial', {
            'line': line,
        })

    # ─── Tab: Exams ────────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/exams',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_exams(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        ExamPaper = request.env['edu.exam.paper'].sudo()
        papers = ExamPaper.search([
            ('batch_id', '=', classroom.batch_id.id),
            ('curriculum_line_id', '=', classroom.curriculum_line_id.id),
        ], order='create_date desc')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='exams',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'papers': papers,
        })
        return request.render('edu_portal.teacher_classroom_exams_page', context)

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/exams/<int:paper_id>',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_exam_marks(self, classroom_id, paper_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        paper = request.env['edu.exam.paper'].sudo().browse(paper_id)
        if not paper.exists() or paper.batch_id != classroom.batch_id \
                or paper.curriculum_line_id != classroom.curriculum_line_id:
            return request.not_found()
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('exam_paper_id', '=', paper.id),
            ('section_id', '=', classroom.section_id.id),
            ('is_latest_attempt', '=', True),
        ])
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='exams',
            classroom=classroom,
            page_title=f'{classroom.name} — {paper.display_name}',
        )
        context.update({
            'employee': employee,
            'paper': paper,
            'marksheets': marksheets,
        })
        return request.render('edu_portal.teacher_classroom_exam_marks_page', context)

    @http.route(
        '/portal/teacher/classroom/exams/save',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_exam_save(self, marksheet_id, marks_obtained, **kw):
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        marksheet = request.env['edu.exam.marksheet'].sudo().browse(int(marksheet_id))
        if not marksheet.exists():
            return request.not_found()
        # Verify the teacher owns a classroom matching this paper's batch/curriculum
        classroom = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', request.env.user.id),
            ('batch_id', '=', marksheet.exam_paper_id.batch_id.id),
            ('curriculum_line_id', '=', marksheet.exam_paper_id.curriculum_line_id.id),
            ('section_id', '=', marksheet.section_id.id),
        ], limit=1)
        if not classroom:
            return request.not_found()
        try:
            marks_value = float(marks_obtained) if marks_obtained else 0.0
        except (TypeError, ValueError):
            return request.not_found()
        if marks_value < 0 or marks_value > marksheet.max_marks:
            return request.render('edu_portal.teacher_marks_row_partial', {
                'marksheet': marksheet,
                'error': f'Invalid marks: must be between 0 and {marksheet.max_marks}',
            })
        marksheet.write({'marks_obtained': marks_value})
        return request.render('edu_portal.teacher_marks_row_partial', {
            'marksheet': marksheet,
            'error': None,
        })

    # ─── Tab: Assessments ──────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/assessments',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_assessments(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc', limit=100)
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='assessments',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'records': records,
        })
        return request.render('edu_portal.teacher_classroom_assessments_page', context)

    # ─── Tab: Results ──────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/results',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_results(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        # Published student results scoped to this section + term
        ResultStudent = request.env['edu.result.student'].sudo()
        results = ResultStudent.search([
            ('section_id', '=', classroom.section_id.id),
            ('program_term_id', '=', classroom.program_term_id.id),
            ('result_session_id.state', 'in', ('published', 'closed')),
        ], order='student_id')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='results',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'results': results,
        })
        return request.render('edu_portal.teacher_classroom_results_page', context)

    # ─── Tab: People ───────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/people',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_people(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        students = histories.mapped('student_id')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='people',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'students': students,
        })
        return request.render('edu_portal.teacher_classroom_people_page', context)
