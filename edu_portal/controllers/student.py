"""Student portal controllers — outside-classroom pages.

Only three routes live here:

* ``/portal/student/home``    — classroom card grid (Google Classroom).
* ``/portal/student/profile`` — the logged-in student's profile page.
* ``/portal/student/fees``    — sidebar link: dues, payments, balance.

Every in-classroom tab is owned by ``student_classroom.py``.
"""
from odoo import http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_student_record,
)


class StudentPortalController(http.Controller):

    def _guard_student(self):
        """Return the student's edu.student record or None if not authorised."""
        user = request.env.user
        if get_portal_role(user) != 'student':
            return None
        return get_student_record(user)

    # ─── Home: classroom grid ──────────────────────────────────

    @http.route('/portal/student/home', type='http', auth='user', website=False)
    def student_home(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')

        # Student's current active progression → section
        history = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
        ], limit=1)
        classroom_cards = []
        if history:
            classrooms = request.env['edu.classroom'].sudo().search([
                ('section_id', '=', history.section_id.id),
            ])
            for cl in classrooms:
                classroom_cards.append({
                    'classroom': cl,
                    'status_label': cl.state.title(),
                    'status_class': (
                        'badge-success' if cl.state == 'active' else 'badge-muted'
                    ),
                    'detail_url': '/portal/student/classroom/%d' % cl.id,
                })

        context = build_portal_context(
            active_sidebar_key='home',
            page_title='Home',
        )
        context.update({
            'student': student,
            'classroom_cards': classroom_cards,
        })
        return request.render('edu_portal.student_home_page', context)

    # ─── Profile ────────────────────────────────────────────────

    @http.route('/portal/student/profile', type='http', auth='user', website=False)
    def student_profile(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        context = build_portal_context(
            active_sidebar_key='profile',
            page_title='My Profile',
        )
        context.update({'student': student})
        return request.render('edu_portal.student_profile_page', context)

    # ─── Fees ───────────────────────────────────────────────────

    @http.route('/portal/student/fees', type='http', auth='user', website=False)
    def student_fees(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        dues = request.env['edu.student.fee.due'].search(
            [('student_id', '=', student.id)], order='due_date',
        )
        payments = request.env['edu.student.payment'].search(
            [('student_id', '=', student.id)], order='payment_date desc',
        )
        total_due = sum(dues.mapped('balance_amount')) if dues else 0.0
        context = build_portal_context(
            active_sidebar_key='fees',
            page_title='My Fees',
        )
        context.update({
            'student': student,
            'dues': dues,
            'payments': payments,
            'total_due': total_due,
        })
        return request.render('edu_portal.student_fees_page', context)
