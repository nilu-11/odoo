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

        # ── Attention queue ──
        attention_items = []
        # Pending marks
        if marks_due_count:
            attention_items.append({
                'kind': 'danger',
                'icon': '!',
                'text': '%d exam paper(s) awaiting marks entry' % marks_due_count,
            })
        # Attendance not taken today
        today_date = fields.Date.today()
        for cl in classrooms:
            if cl.state != 'active' or not cl.attendance_register_id:
                continue
            has_today = request.env['edu.attendance.sheet'].sudo().search_count([
                ('register_id', '=', cl.attendance_register_id.id),
                ('session_date', '=', today_date),
            ])
            if not has_today:
                attention_items.append({
                    'kind': 'warn',
                    'icon': '○',
                    'text': '%s — attendance not taken today' % cl.name,
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
