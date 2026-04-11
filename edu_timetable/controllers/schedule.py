"""Portal schedule controllers for teacher and student.

Renders calendar-style views of timetable slots for the current user.

Teacher: all slots where the user's hr.employee is the teacher_id.
  - Employee is resolved via hr.employee search on user_id (same as
    edu_portal's get_teacher_employee helper).

Student: all slots where the student's active progression section matches.
  - Student is resolved via edu.student search on partner_id (same as
    edu_portal's get_student_record helper).
"""

from odoo import http
from odoo.http import request

from odoo.addons.edu_portal.controllers.helpers import (
    build_portal_context,
    get_portal_role,
    get_teacher_employee,
    get_student_record,
)


class PortalScheduleController(http.Controller):

    # ─── Teacher schedule ──────────────────────────────────────────

    @http.route(
        '/portal/teacher/schedule',
        type='http',
        auth='user',
        website=False,
    )
    def teacher_schedule(self, **kw):
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return request.redirect('/portal')
        employee = get_teacher_employee(user)
        if not employee:
            return request.redirect('/portal')
        slots = request.env['edu.timetable.slot'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('slot_type', '!=', 'cancelled'),
        ], order='day_of_week, period_id')
        context = build_portal_context(
            active_sidebar_key='schedule',
            page_title='My Schedule',
        )
        context.update({
            'employee': employee,
            'slots': slots,
            'role': 'teacher',
        })
        return request.render('edu_timetable.portal_schedule_page', context)

    # ─── Student schedule ──────────────────────────────────────────

    @http.route(
        '/portal/student/schedule',
        type='http',
        auth='user',
        website=False,
    )
    def student_schedule(self, **kw):
        user = request.env.user
        if get_portal_role(user) != 'student':
            return request.redirect('/portal')
        student = get_student_record(user)
        if not student:
            return request.redirect('/portal')
        active_prog = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
        ], limit=1)
        if not active_prog or not active_prog.section_id:
            slots = request.env['edu.timetable.slot'].sudo().browse()
        else:
            slots = request.env['edu.timetable.slot'].sudo().search([
                ('section_id', '=', active_prog.section_id.id),
                ('slot_type', '!=', 'cancelled'),
            ], order='day_of_week, period_id')
        context = build_portal_context(
            active_sidebar_key='schedule',
            page_title='My Schedule',
        )
        context.update({
            'student': student,
            'slots': slots,
            'role': 'student',
        })
        return request.render('edu_timetable.portal_schedule_page', context)
