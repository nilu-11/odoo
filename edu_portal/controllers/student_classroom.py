"""Student in-classroom hub controllers.

Owns every ``/portal/student/classroom/<int:classroom_id>/<tab>`` route.
Each handler guards via ``guard_classroom_access`` and then renders the
corresponding read-only student tab.
"""
from odoo import http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_student_record,
    guard_classroom_access,
)


class StudentClassroomController(http.Controller):

    # ─── Auth plumbing ─────────────────────────────────────────

    def _guard(self, classroom_id):
        """Return (classroom, student) or None if unauthorised."""
        user = request.env.user
        if get_portal_role(user) != 'student':
            return None
        classroom = guard_classroom_access(classroom_id, 'student')
        if not classroom:
            return None
        student = get_student_record(user)
        if not student:
            return None
        return classroom, student

    # ─── Entry point ───────────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>',
        type='http', auth='user', website=False,
    )
    def student_classroom_index(self, classroom_id, **kw):
        return request.redirect(f'/portal/student/classroom/{classroom_id}/stream')

    # ─── Tab: Stream ───────────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/stream',
        type='http', auth='user', website=False,
    )
    def student_classroom_stream(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        posts = request.env['edu.classroom.post'].sudo().search([
            ('classroom_id', '=', classroom.id),
            ('active', '=', True),
        ])
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='stream',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'posts': posts,
        })
        return request.render('edu_portal.student_classroom_stream_page', context)

    # ─── Tab: Attendance ───────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/attendance',
        type='http', auth='user', website=False,
    )
    def student_classroom_attendance(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        lines = request.env['edu.attendance.sheet.line'].sudo().search([
            ('student_id', '=', student.id),
            ('classroom_id', '=', classroom.id),
        ], order='session_date desc', limit=200)
        total = len(lines)
        present = len(lines.filtered(lambda line: line.status == 'present'))
        attendance_pct = round((present / total) * 100, 1) if total else 0.0
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='attendance',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'lines': lines,
            'attendance_pct': attendance_pct,
        })
        return request.render('edu_portal.student_classroom_attendance_page', context)

    # ─── Tab: Exams ────────────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/exams',
        type='http', auth='user', website=False,
    )
    def student_classroom_exams(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('student_id', '=', student.id),
            ('exam_paper_id.batch_id', '=', classroom.batch_id.id),
            ('exam_paper_id.curriculum_line_id', '=', classroom.curriculum_line_id.id),
            ('is_latest_attempt', '=', True),
        ], order='create_date desc')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='exams',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'marksheets': marksheets,
        })
        return request.render('edu_portal.student_classroom_exams_page', context)

    # ─── Tab: Assessments ──────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/assessments',
        type='http', auth='user', website=False,
    )
    def student_classroom_assessments(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('student_id', '=', student.id),
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc', limit=200)
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='assessments',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'records': records,
        })
        return request.render('edu_portal.student_classroom_assessments_page', context)

    # ─── Tab: Results ──────────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/results',
        type='http', auth='user', website=False,
    )
    def student_classroom_results(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        ResultStudent = request.env['edu.result.student'].sudo()
        results = ResultStudent.search([
            ('student_id', '=', student.id),
            ('section_id', '=', classroom.section_id.id),
            ('program_term_id', '=', classroom.program_term_id.id),
            ('result_session_id.state', 'in', ('published', 'closed')),
        ], order='create_date desc')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='results',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'results': results,
        })
        return request.render('edu_portal.student_classroom_results_page', context)

    # ─── Tab: People ───────────────────────────────────────────

    @http.route(
        '/portal/student/classroom/<int:classroom_id>/people',
        type='http', auth='user', website=False,
    )
    def student_classroom_people(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, student = guard
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        classmates = histories.mapped('student_id')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='people',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'student': student,
            'classmates': classmates,
        })
        return request.render('edu_portal.student_classroom_people_page', context)
