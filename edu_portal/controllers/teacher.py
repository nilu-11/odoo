"""Teacher portal controllers — outside-classroom pages.

Routes:
* ``/portal/teacher/home`` — Today dashboard with schedule, tasks, courses.
* ``/portal/teacher/profile`` — the logged-in teacher's own profile page.

Every in-classroom tab (Stream, Attendance, Exams, Assessments, Results,
People) is owned by ``teacher_classroom.py``.
"""
from datetime import date

from odoo import fields, http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_teacher_employee,
)


class TeacherPortalController(http.Controller):

    def _guard_teacher(self):
        """Return the teacher's hr.employee or None if not authorised."""
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        return get_teacher_employee(user)

    # ─── Home: Today dashboard ───────────────────────────────────

    @http.route('/portal/teacher/home', type='http', auth='user', website=False)
    def teacher_home(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')

        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])

        # ── Marks due check (batch query) ──
        batch_ids = [cl.batch_id.id for cl in classrooms if cl.batch_id]
        cl_line_ids = [cl.curriculum_line_id.id for cl in classrooms if cl.curriculum_line_id]
        if batch_ids and cl_line_ids:
            papers = ExamPaper.search_read(
                [
                    ('batch_id', 'in', batch_ids),
                    ('curriculum_line_id', 'in', cl_line_ids),
                    ('state', '=', 'marks_entry'),
                ],
                fields=['batch_id', 'curriculum_line_id'],
            )
            marks_due_keys = {
                (p['batch_id'][0], p['curriculum_line_id'][0]) for p in papers
            }
        else:
            marks_due_keys = set()

        marks_due_count = len(marks_due_keys)

        classroom_cards = []
        total_students = 0
        for cl in classrooms:
            marks_due = (cl.batch_id.id, cl.curriculum_line_id.id) in marks_due_keys
            if marks_due:
                status_label, status_class = 'Marks Due', 'badge-danger'
            elif cl.state == 'active':
                status_label, status_class = 'Active', 'badge-success'
            else:
                status_label, status_class = cl.state.title(), 'badge-muted'
            total_students += cl.student_count or 0
            classroom_cards.append({
                'classroom': cl,
                'status_label': status_label,
                'status_class': status_class,
                'detail_url': '/portal/teacher/classroom/%d' % cl.id,
            })

        # ── Today's schedule (soft check for edu_timetable) ──
        today_slots = []
        if 'edu.timetable.slot' in request.env:
            today = date.today()
            day_of_week = str(today.weekday())  # 0=Mon, 6=Sun
            slots = request.env['edu.timetable.slot'].sudo().search([
                ('teacher_id', '=', employee.id),
                ('day_of_week', '=', day_of_week),
                ('slot_type', '!=', 'cancelled'),
            ], order='period_id')
            for slot in slots:
                period = slot.period_id
                today_slots.append({
                    'time': '%s – %s' % (
                        period.time_from if period else '?',
                        period.time_to if period else '?',
                    ),
                    'title': slot.subject_id.name or slot.name or 'Class',
                    'room': slot.room_id.name if slot.room_id else '',
                    'section': slot.section_id.name if slot.section_id else '',
                    'classroom_id': slot.classroom_id.id if slot.classroom_id else False,
                    'slot_type': slot.slot_type,
                })

        # ── Attention queue (matches Kopilā design) ──
        attention_items = []
        today_date = fields.Date.today()

        # Pending marks (featured item)
        if marks_due_count:
            attention_items.append({
                'text': '%d paper(s) to mark' % marks_due_count,
                'detail': 'Marks entry pending',
                'url': '/portal/teacher/marking',
                'featured': True,
            })

        # Attendance not taken today
        for cl in classrooms:
            if cl.state != 'active' or not cl.attendance_register_id:
                continue
            has_today = request.env['edu.attendance.sheet'].sudo().search_count([
                ('register_id', '=', cl.attendance_register_id.id),
                ('session_date', '=', today_date),
            ])
            if not has_today:
                attention_items.append({
                    'text': '%s — attendance not taken' % cl.name,
                    'detail': 'Today',
                    'url': '/portal/teacher/classroom/%d/attendance' % cl.id,
                })

        context = build_portal_context(
            active_sidebar_key='home',
            page_title='Today',
        )
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
            'today_slots': today_slots,
            'attention_items': attention_items,
            'total_students': total_students,
            'total_courses': len(classrooms),
            'marks_due_count': marks_due_count,
            'sessions_today': len(today_slots),
            'today_date': today_date,
        })
        return request.render('edu_portal.teacher_home_page', context)

    # ─── Courses: classroom grid (dedicated page) ──────────────

    @http.route('/portal/teacher/courses', type='http', auth='user', website=False)
    def teacher_courses(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])
        classroom_cards = []
        for cl in classrooms:
            if cl.state == 'active':
                status_label, status_class = 'Active', 'badge-success'
            else:
                status_label, status_class = cl.state.title(), 'badge-muted'
            classroom_cards.append({
                'classroom': cl,
                'status_label': status_label,
                'status_class': status_class,
                'detail_url': '/portal/teacher/classroom/%d' % cl.id,
            })
        context = build_portal_context(
            active_sidebar_key='courses',
            page_title='Courses',
        )
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
        })
        return request.render('edu_portal.teacher_courses_page', context)

    # ─── Attendance: cross-classroom overview ─────────────────

    @http.route('/portal/teacher/attendance', type='http', auth='user', website=False)
    def teacher_attendance(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        classrooms = Classroom.search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])
        today_date = fields.Date.today()
        classroom_att = []
        for cl in classrooms:
            has_today = False
            if cl.attendance_register_id:
                has_today = bool(request.env['edu.attendance.sheet'].sudo().search_count([
                    ('register_id', '=', cl.attendance_register_id.id),
                    ('session_date', '=', today_date),
                    ('state', '=', 'submitted'),
                ]))
            classroom_att.append({
                'classroom': cl,
                'today_done': has_today,
                'url': '/portal/teacher/classroom/%d/attendance' % cl.id,
            })
        context = build_portal_context(
            active_sidebar_key='attendance',
            page_title='Attendance',
        )
        context.update({
            'employee': employee,
            'classroom_att': classroom_att,
            'today_date': today_date,
        })
        return request.render('edu_portal.teacher_attendance_overview_page', context)

    # ─── Marking: exams needing marks ─────────────────────────

    @http.route('/portal/teacher/marking', type='http', auth='user', website=False)
    def teacher_marking(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])
        batch_ids = [cl.batch_id.id for cl in classrooms if cl.batch_id]
        cl_line_ids = [cl.curriculum_line_id.id for cl in classrooms if cl.curriculum_line_id]
        papers = ExamPaper.browse()
        if batch_ids and cl_line_ids:
            papers = ExamPaper.search([
                ('batch_id', 'in', batch_ids),
                ('curriculum_line_id', 'in', cl_line_ids),
                ('state', '=', 'marks_entry'),
            ])
        context = build_portal_context(
            active_sidebar_key='marking',
            page_title='Marking',
        )
        context.update({
            'employee': employee,
            'papers': papers,
            'classrooms': classrooms,
        })
        return request.render('edu_portal.teacher_marking_overview_page', context)

    # ─── Gradebook: redirect to first classroom results ───────

    @http.route('/portal/teacher/gradebook', type='http', auth='user', website=False)
    def teacher_gradebook(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])
        classroom_cards = []
        for cl in classrooms:
            classroom_cards.append({
                'classroom': cl,
                'url': '/portal/teacher/classroom/%d/results' % cl.id,
            })
        context = build_portal_context(
            active_sidebar_key='gradebook',
            page_title='Gradebook',
        )
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
        })
        return request.render('edu_portal.teacher_gradebook_overview_page', context)

    # ─── Report Cards: placeholder ────────────────────────────

    @http.route('/portal/teacher/reports', type='http', auth='user', website=False)
    def teacher_reports(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        context = build_portal_context(
            active_sidebar_key='reports',
            page_title='Report Cards',
        )
        context.update({'employee': employee})
        return request.render('edu_portal.teacher_reports_overview_page', context)

    # ─── Calendar (hold — placeholder) ─────────────────────────

    @http.route('/portal/teacher/calendar', type='http', auth='user', website=False)
    def teacher_calendar(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        context = build_portal_context(
            active_sidebar_key='calendar',
            page_title='Calendar',
        )
        context.update({'employee': employee})
        return request.render('edu_portal.teacher_calendar_page', context)

    # ─── Profile ────────────────────────────────────────────────

    @http.route('/portal/teacher/profile', type='http', auth='user', website=False)
    def teacher_profile(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        context = build_portal_context(
            active_sidebar_key='profile',
            page_title='My Profile',
        )
        context.update({'employee': employee})
        return request.render('edu_portal.teacher_profile_page', context)
