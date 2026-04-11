"""Teacher portal controllers — outside-classroom pages.

Only two routes live here:

* ``/portal/teacher/home`` — pure classroom card grid, Google Classroom
  style. No stats strip, no dashboard widgets.
* ``/portal/teacher/profile`` — the logged-in teacher's own profile page.

Every in-classroom tab (Stream, Attendance, Exams, Assessments, Results,
People) is owned by ``teacher_classroom.py``.
"""
from odoo import http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_teacher_employee,
)


class TeacherPortalController(http.Controller):

    def _guard_teacher(self):
        """Return the teacher's hr.employee or None if not authorised.

        NOTE: the returned employee is for display only. Auth comparisons
        against classroom.teacher_id / exam_paper.teacher_id must use
        ``request.env.user`` — those fields are m2o to res.users.
        """
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        return get_teacher_employee(user)

    # ─── Home: classroom grid ──────────────────────────────────

    @http.route('/portal/teacher/home', type='http', auth='user', website=False)
    def teacher_home(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')

        # Classrooms owned by the current user (teacher_id is res.users)
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', request.env.user.id)])

        classroom_cards = []
        for cl in classrooms:
            marks_due = ExamPaper.search_count([
                ('batch_id', '=', cl.batch_id.id),
                ('curriculum_line_id', '=', cl.curriculum_line_id.id),
                ('state', '=', 'marks_entry'),
            ])
            if marks_due:
                status_label, status_class = 'Marks Due', 'badge-danger'
            elif cl.state == 'active':
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
            active_sidebar_key='home',
            page_title='Home',
        )
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
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
