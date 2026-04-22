import logging
from datetime import date

from odoo import http
from odoo.http import request

from .helpers import (
    get_portal_role,
    get_guardian_record,
    get_parent_children,
    get_active_child,
    build_portal_context,
)

_logger = logging.getLogger(__name__)


class EduPortalParent(http.Controller):
    """Parent portal routes — all data is scoped to the active child."""

    # ── Guard helper ───────────────────────────────────────────────────────

    def _check_parent(self):
        """Return (guardian, active_child, error_response) tuple.

        If the user is not a parent or has no children, error_response is set.
        """
        user = request.env.user
        role = get_portal_role(user)
        if role != 'parent':
            return None, None, request.redirect('/portal')
        guardian = get_guardian_record(user)
        if not guardian:
            return None, None, request.redirect('/portal')
        child = get_active_child(user)
        return guardian, child, None

    # ══════════════════════════════════════════════════════════════════════
    # Home — Children overview
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/home', type='http', auth='user', website=False)
    def parent_home(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        children = get_parent_children(request.env.user)

        # Build children_list dicts matching the template's expected structure
        children_list = []
        for c in children:
            histories = request.env['edu.student.progression.history'].sudo().search([
                ('student_id', '=', c.id),
                ('state', '=', 'active'),
            ])
            section_ids = histories.mapped('section_id').ids

            classrooms = request.env['edu.classroom'].sudo()
            if section_ids:
                classrooms = request.env['edu.classroom'].sudo().search([
                    ('section_id', 'in', section_ids),
                    ('state', '=', 'active'),
                ], order='name')

            due_count = request.env['edu.student.fee.due'].sudo().search_count([
                ('student_id', '=', c.id),
                ('state', 'in', ('due', 'partial', 'overdue')),
            ])

            name = c.partner_id.name if c.partner_id else (c.display_name or '')
            words = [w for w in name.split() if w]
            initials = (''.join(w[0] for w in words[:2])).upper() or '?'

            courses = [
                {'code': cl.code or '', 'attendance_pct': 0, 'color': 'saffron'}
                for cl in classrooms
            ]

            children_list.append({
                'id': c.id,
                'name': name,
                'initials': initials,
                'hue': 60,
                'student_id': c.student_no or '',
                'program': histories[0].batch_id.name if histories and histories[0].batch_id else '',
                'attendance': '—',
                'gpa': '—',
                'fees_status': '%d due' % due_count if due_count else 'Clear',
                'courses': courses,
                'first_name': words[0] if words else name,
            })

        user_name = (request.env.user.name or '').split()
        parent_first_name = user_name[0] if user_name else 'Parent'

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='home',
            page_title='Overview',
            crumbs=['Kopila', 'Overview'],
            guardian=guardian,
            children_list=children_list,
            parent_first_name=parent_first_name,
            today_date_label=date.today().strftime('%A, %B %-d %Y'),
            parent_activity=[],
            parent_behavior_notes=[],
        )
        return request.render('edu_portal.parent_home', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Attendance — Active child's attendance
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/attendance', type='http', auth='user',
                website=False)
    def parent_attendance(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        attendance_data = []
        if child:
            # Get all classrooms for this child
            histories = request.env['edu.student.progression.history'].sudo().search([
                ('student_id', '=', child.id),
                ('state', '=', 'active'),
            ])
            section_ids = histories.mapped('section_id').ids

            classrooms = request.env['edu.classroom'].sudo()
            if section_ids:
                classrooms = request.env['edu.classroom'].sudo().search([
                    ('section_id', 'in', section_ids),
                    ('state', '=', 'active'),
                ], order='name')

            for cl in classrooms:
                register = getattr(cl, 'attendance_register_id', False)
                summary = {'total': 0, 'present': 0, 'percent': 0.0}
                if register:
                    try:
                        full_summary = register.get_student_attendance_summary()
                        summary = full_summary.get(child.id, summary)
                    except Exception:
                        pass

                attendance_data.append({
                    'classroom': cl,
                    'summary': summary,
                })

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='attendance',
            page_title='Attendance',
            crumbs=['Kopila', 'Attendance'],
            guardian=guardian,
            student=child,
            attendance_data=attendance_data,
        )
        return request.render('edu_portal.parent_attendance', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Results — Active child's results
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/results', type='http', auth='user',
                website=False)
    def parent_results(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        student_results = request.env['edu.result.student'].sudo()
        subject_lines = request.env['edu.result.subject.line'].sudo()

        if child:
            student_results = request.env['edu.result.student'].sudo().search([
                ('student_id', '=', child.id),
                ('result_session_id.state', 'in', ('published', 'closed')),
            ], order='result_session_id desc')

            if student_results:
                result_session_ids = student_results.mapped('result_session_id').ids
                subject_lines = request.env['edu.result.subject.line'].sudo().search([
                    ('student_id', '=', child.id),
                    ('result_session_id', 'in', result_session_ids),
                ], order='result_session_id desc, subject_id')

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='results',
            page_title='Results',
            crumbs=['Kopila', 'Results'],
            guardian=guardian,
            student=child,
            student_results=student_results,
            subject_lines=subject_lines,
        )
        return request.render('edu_portal.parent_results', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Assessments — Active child's assessments
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/assessments', type='http', auth='user',
                website=False)
    def parent_assessments(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        records = request.env['edu.continuous.assessment.record'].sudo()
        if child:
            records = request.env['edu.continuous.assessment.record'].sudo().search([
                ('student_id', '=', child.id),
            ], order='assessment_date desc', limit=50)

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='assessments',
            page_title='Assessments',
            crumbs=['Kopila', 'Assessments'],
            guardian=guardian,
            student=child,
            records=records,
        )
        return request.render('edu_portal.parent_assessments', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Fees — Active child's fees
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/fees', type='http', auth='user', website=False)
    def parent_fees(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        fee_plans = request.env['edu.student.fee.plan'].sudo()
        dues = request.env['edu.student.fee.due'].sudo()
        payments = request.env['edu.student.payment'].sudo()

        if child:
            fee_plans = request.env['edu.student.fee.plan'].sudo().search([
                ('student_id', '=', child.id),
            ], order='create_date desc')

            dues = request.env['edu.student.fee.due'].sudo().search([
                ('student_id', '=', child.id),
                ('state', 'in', ('due', 'partial', 'overdue')),
            ], order='due_date')

            payments = request.env['edu.student.payment'].sudo().search([
                ('student_id', '=', child.id),
                ('state', '=', 'posted'),
            ], order='payment_date desc', limit=20)

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='fees',
            page_title='Fees',
            crumbs=['Kopila', 'Fees'],
            guardian=guardian,
            student=child,
            fee_plans=fee_plans,
            dues=dues,
            payments=payments,
        )
        return request.render('edu_portal.parent_fees', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Profile — Guardian profile
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/parent/profile', type='http', auth='user',
                website=False)
    def parent_profile(self, **kw):
        guardian, child, err = self._check_parent()
        if err:
            return err

        children = get_parent_children(request.env.user)

        ctx = build_portal_context(
            'parent',
            active_sidebar_key='profile',
            page_title='My Profile',
            crumbs=['Kopila', 'My Profile'],
            guardian=guardian,
            student=child,
            all_children=children,
        )
        return request.render('edu_portal.parent_profile', ctx)
