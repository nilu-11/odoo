import logging
from datetime import date

from odoo import http, fields
from odoo.http import request

from .helpers import (
    get_portal_role,
    get_teacher_employee,
    build_portal_context,
)

_logger = logging.getLogger(__name__)


class EduPortalTeacher(http.Controller):
    """Teacher outside-classroom portal routes."""

    # ── Guard helper ───────────────────────────────────────────────────────

    def _check_teacher(self):
        """Return (employee, error_response) tuple.

        If the user is not a teacher, error_response is a redirect.
        Otherwise error_response is None and employee is the hr.employee record.
        """
        user = request.env.user
        role = get_portal_role(user)
        if role != 'teacher':
            return None, request.redirect('/portal')
        employee = get_teacher_employee(user)
        if not employee:
            return None, request.redirect('/portal')
        return employee, None

    # ══════════════════════════════════════════════════════════════════════
    # Today Dashboard
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/home', type='http', auth='user', website=False)
    def teacher_home(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        today = date.today()

        # Active classrooms for this teacher
        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ], order='name')

        # Today's attendance sheets (across all classrooms)
        today_sheets = request.env['edu.attendance.sheet'].sudo()
        register_ids = []
        for cl in classrooms:
            reg = getattr(cl, 'attendance_register_id', False)
            if reg:
                register_ids.append(reg.id)
        if register_ids:
            today_sheets = request.env['edu.attendance.sheet'].sudo().search([
                ('register_id', 'in', register_ids),
                ('session_date', '=', today),
            ], order='time_from')

        # Papers needing marks entry
        papers_marking = request.env['edu.exam.paper'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ], limit=10)

        # Recent announcements (classroom posts)
        recent_posts = request.env['edu.classroom.post'].sudo()
        if classrooms:
            recent_posts = request.env['edu.classroom.post'].sudo().search([
                ('classroom_id', 'in', classrooms.ids),
                ('active', '=', True),
            ], order='posted_at desc', limit=5)

        attention_items = [
            {
                'url': '/portal/teacher/marking',
                'label': p.display_name or 'Exam paper',
                'detail': 'Awaiting marks entry',
            }
            for p in papers_marking[:6]
        ]

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='today',
            page_title='Today',
            crumbs=['Kopila', 'Today'],
            today=today,
            classrooms=classrooms,
            today_sheets=today_sheets,
            papers_marking=papers_marking,
            recent_posts=recent_posts,
            today_date_label=today.strftime('%A, %B %-d %Y'),
            today_nepali_label='',
            today_day_name=today.strftime('%A'),
            today_events_count=0,
            teacher_first_name=(employee.name or '').split()[0] or 'Teacher',
            classes_today_count=len(today_sheets),
            total_to_grade=len(papers_marking),
            unread_messages=0,
            attention_items=attention_items,
            attention_highlight={
                'url': '/portal/teacher/marking',
                'label': '%d paper%s awaiting marks' % (len(papers_marking), 's' if len(papers_marking) != 1 else ''),
                'detail': 'Click to open marking queue',
            } if papers_marking else None,
        )
        return request.render('edu_portal.teacher_home', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Courses
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/courses', type='http', auth='user', website=False)
    def teacher_courses(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ], order='batch_id, section_id, name')

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='courses',
            page_title='Courses',
            crumbs=['Kopila', 'Courses'],
            classrooms=classrooms,
        )
        return request.render('edu_portal.teacher_courses', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Attendance Overview (cross-classroom)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/attendance', type='http', auth='user',
                website=False)
    def teacher_attendance(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ], order='name')

        # Gather attendance registers for teacher's classrooms
        registers = request.env['edu.attendance.register'].sudo()
        for cl in classrooms:
            reg = getattr(cl, 'attendance_register_id', False)
            if reg:
                registers |= reg

        # Recent sheets across all registers
        recent_sheets = request.env['edu.attendance.sheet'].sudo()
        if registers:
            recent_sheets = request.env['edu.attendance.sheet'].sudo().search([
                ('register_id', 'in', registers.ids),
            ], order='session_date desc, time_from desc', limit=20)

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='attendance',
            page_title='Attendance',
            crumbs=['Kopila', 'Attendance'],
            classrooms=classrooms,
            registers=registers,
            recent_sheets=recent_sheets,
        )
        return request.render('edu_portal.teacher_attendance', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Marking (papers needing marks)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/marking', type='http', auth='user',
                website=False)
    def teacher_marking(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        # Papers in marks_entry state for this teacher
        papers = request.env['edu.exam.paper'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ], order='exam_date, subject_id')

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='marking',
            page_title='Marking',
            crumbs=['Kopila', 'Marking'],
            papers=papers,
        )
        return request.render('edu_portal.teacher_marking', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Gradebook
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/gradebook', type='http', auth='user',
                website=False)
    def teacher_gradebook(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ], order='name', limit=1)

        # Redirect to first classroom's results tab if available
        if classrooms:
            return request.redirect(
                '/portal/teacher/classroom/%d/results' % classrooms[0].id
            )

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='gradebook',
            page_title='Gradebook',
            crumbs=['Kopila', 'Gradebook'],
        )
        return request.render('edu_portal.teacher_gradebook', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Report Cards (placeholder)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/reports', type='http', auth='user',
                website=False)
    def teacher_reports(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        # Published result sessions for the teacher's classrooms
        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])
        batch_ids = classrooms.mapped('batch_id').ids
        result_sessions = request.env['edu.result.session'].sudo()
        if batch_ids:
            result_sessions = request.env['edu.result.session'].sudo().search([
                ('batch_id', 'in', batch_ids),
                ('state', 'in', ('published', 'closed')),
            ], order='name desc', limit=20)

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='reports',
            page_title='Report Cards',
            crumbs=['Kopila', 'Report Cards'],
            result_sessions=result_sessions,
        )
        return request.render('edu_portal.teacher_reports', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Messages (placeholder)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/messages', type='http', auth='user',
                website=False)
    def teacher_messages(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='messages',
            page_title='Messages',
            crumbs=['Kopila', 'Messages'],
        )
        return request.render('edu_portal.teacher_messages', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Announcements
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/announcements', type='http', auth='user',
                website=False)
    def teacher_announcements(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])

        posts = request.env['edu.classroom.post'].sudo()
        if classrooms:
            posts = request.env['edu.classroom.post'].sudo().search([
                ('classroom_id', 'in', classrooms.ids),
                ('active', '=', True),
            ], order='pinned desc, posted_at desc', limit=50)

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='announcements',
            page_title='Announcements',
            crumbs=['Kopila', 'Announcements'],
            classrooms=classrooms,
            posts=posts,
        )
        return request.render('edu_portal.teacher_announcements', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Calendar (placeholder)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/calendar', type='http', auth='user',
                website=False)
    def teacher_calendar(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='calendar',
            page_title='Calendar',
            crumbs=['Kopila', 'Calendar'],
        )
        return request.render('edu_portal.teacher_calendar', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Behavior Notes (placeholder)
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/behavior', type='http', auth='user',
                website=False)
    def teacher_behavior(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='behavior',
            page_title='Behavior Notes',
            crumbs=['Kopila', 'Behavior Notes'],
        )
        return request.render('edu_portal.teacher_behavior', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Fees Overview
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/fees', type='http', auth='user', website=False)
    def teacher_fees(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        classrooms = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])

        # Get section student IDs for fee overview
        section_ids = classrooms.mapped('section_id').ids
        histories = request.env['edu.student.progression.history'].sudo()
        if section_ids:
            histories = request.env['edu.student.progression.history'].sudo().search([
                ('section_id', 'in', section_ids),
                ('state', '=', 'active'),
            ])
        student_ids = histories.mapped('student_id').ids

        # Fee dues summary for those students
        dues = request.env['edu.student.fee.due'].sudo()
        if student_ids:
            dues = request.env['edu.student.fee.due'].sudo().search([
                ('student_id', 'in', student_ids),
                ('state', 'in', ('due', 'partial', 'overdue')),
            ], order='due_date')

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='fees',
            page_title='Fees Overview',
            crumbs=['Kopila', 'Fees Overview'],
            classrooms=classrooms,
            dues=dues,
        )
        return request.render('edu_portal.teacher_fees', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Teacher Profile
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/profile', type='http', auth='user',
                website=False)
    def teacher_profile(self, **kw):
        employee, err = self._check_teacher()
        if err:
            return err

        ctx = build_portal_context(
            'teacher',
            active_sidebar_key='profile',
            page_title='My Profile',
            crumbs=['Kopila', 'My Profile'],
            employee=employee,
        )
        return request.render('edu_portal.teacher_profile', ctx)
