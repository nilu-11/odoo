import logging

from odoo import http
from odoo.http import request

from .helpers import (
    get_portal_role,
    get_student_record,
    guard_classroom_access,
    build_portal_context,
    get_section_students,
)

_logger = logging.getLogger(__name__)


class EduPortalStudentClassroom(http.Controller):
    """Student in-classroom portal routes (read-only, 6 tabs)."""

    # ── Common guard ───────────────────────────────────────────────────────

    def _guard(self, classroom_id):
        """Return (classroom, student, error) tuple."""
        user = request.env.user
        role = get_portal_role(user)
        if role != 'student':
            return None, None, request.redirect('/portal')
        student = get_student_record(user)
        if not student:
            return None, None, request.redirect('/portal')
        classroom = guard_classroom_access(classroom_id, 'student')
        if not classroom:
            return None, None, request.not_found()
        return classroom, student, None

    # ══════════════════════════════════════════════════════════════════════
    # Root redirect
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>', type='http',
                auth='user', website=False)
    def student_classroom_root(self, classroom_id, **kw):
        return request.redirect(
            '/portal/student/classroom/%d/stream' % classroom_id
        )

    # ══════════════════════════════════════════════════════════════════════
    # Tab 1: Stream (read-only)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/stream',
                type='http', auth='user', website=False)
    def student_classroom_stream(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        posts = request.env['edu.classroom.post'].sudo().search([
            ('classroom_id', '=', classroom.id),
            ('active', '=', True),
        ], order='pinned desc, posted_at desc')

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='stream',
            active_sidebar_key='courses',
            page_title=classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Stream'],
            posts=posts,
            student=student,
        )
        return request.render('edu_portal.student_classroom_stream', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 2: Attendance (own attendance %)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/attendance',
                type='http', auth='user', website=False)
    def student_classroom_attendance(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        register = getattr(classroom, 'attendance_register_id', False)
        student_summary = {}
        attendance_lines = request.env['edu.attendance.sheet.line'].sudo()

        if register:
            # Get this student's attendance summary
            try:
                full_summary = register.get_student_attendance_summary()
                student_summary = full_summary.get(student.id, {
                    'total': 0, 'present': 0, 'percent': 0.0,
                })
            except Exception:
                _logger.warning(
                    'Could not compute attendance summary for student %s',
                    student.id, exc_info=True,
                )

            # Get individual attendance lines for this student
            attendance_lines = request.env['edu.attendance.sheet.line'].sudo().search([
                ('register_id', '=', register.id),
                ('student_id', '=', student.id),
                ('sheet_state', '=', 'submitted'),
            ], order='session_date desc')

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='attendance',
            active_sidebar_key='courses',
            page_title='%s - Attendance' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Attendance'],
            student=student,
            student_summary=student_summary,
            attendance_lines=attendance_lines,
        )
        return request.render('edu_portal.student_classroom_attendance', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 3: Exams (own marksheets)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/exams',
                type='http', auth='user', website=False)
    def student_classroom_exams(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        # Only show marksheets from published or closed papers
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('student_id', '=', student.id),
            ('exam_paper_id.classroom_id', '=', classroom.id),
            ('exam_paper_state', 'in', ('published', 'closed')),
            ('is_latest_attempt', '=', True),
        ], order='exam_paper_id')

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='exams',
            active_sidebar_key='courses',
            page_title='%s - Exams' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Exams'],
            student=student,
            marksheets=marksheets,
        )
        return request.render('edu_portal.student_classroom_exams', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 4: Assessments (own assessments)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/assessments',
                type='http', auth='user', website=False)
    def student_classroom_assessments(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('student_id', '=', student.id),
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc')

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='assessments',
            active_sidebar_key='courses',
            page_title='%s - Assessments' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Assessments'],
            student=student,
            records=records,
        )
        return request.render('edu_portal.student_classroom_assessments', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 5: Results (own results)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/results',
                type='http', auth='user', website=False)
    def student_classroom_results(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        # Published result subject lines for this student in this subject
        subject_lines = request.env['edu.result.subject.line'].sudo().search([
            ('student_id', '=', student.id),
            ('subject_id', '=', classroom.subject_id.id),
            ('section_id', '=', classroom.section_id.id),
            ('result_session_id.state', 'in', ('published', 'closed')),
        ], order='result_session_id desc')

        # Overall student results for published sessions in this batch/term
        student_results = request.env['edu.result.student'].sudo().search([
            ('student_id', '=', student.id),
            ('batch_id', '=', classroom.batch_id.id),
            ('program_term_id', '=', classroom.program_term_id.id),
            ('result_session_id.state', 'in', ('published', 'closed')),
        ], order='result_session_id desc')

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='results',
            active_sidebar_key='courses',
            page_title='%s - Results' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Results'],
            student=student,
            subject_lines=subject_lines,
            student_results=student_results,
        )
        return request.render('edu_portal.student_classroom_results', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 6: People (classmates)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/classroom/<int:classroom_id>/people',
                type='http', auth='user', website=False)
    def student_classroom_people(self, classroom_id, **kw):
        classroom, student, err = self._guard(classroom_id)
        if err:
            return err

        classmates = get_section_students(classroom.section_id)

        # Teacher info
        teacher = classroom.teacher_id  # hr.employee record

        ctx = build_portal_context(
            'student',
            classroom=classroom,
            active_tab_key='people',
            active_sidebar_key='courses',
            page_title='%s - People' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'People'],
            student=student,
            classmates=classmates,
            teacher_employee=teacher,
        )
        return request.render('edu_portal.student_classroom_people', ctx)
