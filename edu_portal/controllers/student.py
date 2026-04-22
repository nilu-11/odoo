import logging

from odoo import http
from odoo.http import request

from .helpers import (
    get_portal_role,
    get_student_record,
    build_portal_context,
)

_logger = logging.getLogger(__name__)


class EduPortalStudent(http.Controller):
    """Student outside-classroom portal routes."""

    # ── Guard helper ───────────────────────────────────────────────────────

    def _check_student(self):
        """Return (student, error_response) tuple.

        If the user is not a student, error_response is a redirect.
        Otherwise error_response is None and student is the edu.student record.
        """
        user = request.env.user
        role = get_portal_role(user)
        if role != 'student':
            return None, request.redirect('/portal')
        student = get_student_record(user)
        if not student:
            return None, request.redirect('/portal')
        return student, None

    # ══════════════════════════════════════════════════════════════════════
    # Home — Classroom card grid
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/home', type='http', auth='user', website=False)
    def student_home(self, **kw):
        student, err = self._check_student()
        if err:
            return err

        # Get active progression histories to find classrooms
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
        ])
        section_ids = histories.mapped('section_id').ids

        # Find all active classrooms in the student's sections
        classrooms = request.env['edu.classroom'].sudo()
        if section_ids:
            classrooms = request.env['edu.classroom'].sudo().search([
                ('section_id', 'in', section_ids),
                ('state', '=', 'active'),
            ], order='name')

        ctx = build_portal_context(
            'student',
            active_sidebar_key='home',
            page_title='Home',
            crumbs=['Kopila', 'Home'],
            student=student,
            classrooms=classrooms,
            histories=histories,
        )
        return request.render('edu_portal.student_home', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Courses
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/courses', type='http', auth='user',
                website=False)
    def student_courses(self, **kw):
        student, err = self._check_student()
        if err:
            return err

        histories = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
        ])
        section_ids = histories.mapped('section_id').ids

        classrooms = request.env['edu.classroom'].sudo()
        if section_ids:
            classrooms = request.env['edu.classroom'].sudo().search([
                ('section_id', 'in', section_ids),
                ('state', '=', 'active'),
            ], order='batch_id, section_id, name')

        ctx = build_portal_context(
            'student',
            active_sidebar_key='courses',
            page_title='Courses',
            crumbs=['Kopila', 'Courses'],
            student=student,
            classrooms=classrooms,
        )
        return request.render('edu_portal.student_courses', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Fees
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/fees', type='http', auth='user', website=False)
    def student_fees(self, **kw):
        student, err = self._check_student()
        if err:
            return err

        # Fee plans for this student
        fee_plans = request.env['edu.student.fee.plan'].sudo().search([
            ('student_id', '=', student.id),
        ], order='create_date desc')

        # Outstanding dues
        dues = request.env['edu.student.fee.due'].sudo().search([
            ('student_id', '=', student.id),
            ('state', 'in', ('due', 'partial', 'overdue')),
        ], order='due_date')

        # Recent payments
        payments = request.env['edu.student.payment'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'posted'),
        ], order='payment_date desc', limit=20)

        ctx = build_portal_context(
            'student',
            active_sidebar_key='fees',
            page_title='Fees',
            crumbs=['Kopila', 'Fees'],
            student=student,
            fee_plans=fee_plans,
            dues=dues,
            payments=payments,
        )
        return request.render('edu_portal.student_fees', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Profile
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/student/profile', type='http', auth='user',
                website=False)
    def student_profile(self, **kw):
        student, err = self._check_student()
        if err:
            return err

        # Active progression context
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
        ])

        ctx = build_portal_context(
            'student',
            active_sidebar_key='profile',
            page_title='My Profile',
            crumbs=['Kopila', 'My Profile'],
            student=student,
            histories=histories,
        )
        return request.render('edu_portal.student_profile', ctx)
