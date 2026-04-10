"""Parent portal controllers."""
from odoo import http
from odoo.http import request
from .helpers import (
    base_context, get_guardian_record, get_parent_children, get_active_child, get_portal_role,
)


class ParentPortalController(http.Controller):

    def _guard_parent(self):
        user = request.env.user
        if get_portal_role(user) != 'parent':
            return None
        return get_guardian_record(user)

    def _parent_sidebar_items(self, guardian, active=None):
        return [
            {'key': 'home',        'label': 'Overview',    'icon': '🏠', 'url': '/portal/parent/home'},
            {'key': 'attendance',  'label': 'Attendance',  'icon': '✓', 'url': '/portal/parent/attendance'},
            {'key': 'results',     'label': 'Results',     'icon': '📊', 'url': '/portal/parent/results'},
            {'key': 'assessments', 'label': 'Assessments', 'icon': '📝', 'url': '/portal/parent/assessments'},
            {'key': 'fees',        'label': 'Fees',        'icon': '💰', 'url': '/portal/parent/fees'},
            {'key': 'profile',     'label': 'Profile',     'icon': '👤', 'url': '/portal/parent/profile'},
        ]

    def _base_parent_context(self, active_item, page_title):
        user = request.env.user
        guardian = self._guard_parent()
        children = get_parent_children(user)
        active_child = get_active_child(user)
        context = base_context(active_item=active_item, page_title=page_title)
        context.update({
            'guardian': guardian,
            'children': children,
            'active_child': active_child,
            'sidebar_items': self._parent_sidebar_items(guardian, active_item),
        })
        return context

    @http.route('/portal/parent/home', type='http', auth='user', website=False)
    def parent_home(self, **kw):
        user = request.env.user
        if not self._guard_parent():
            return request.redirect('/portal')
        children = get_parent_children(user)
        # Build per-child summary
        summaries = []
        for child in children:
            lines = request.env['edu.attendance.sheet.line'].search(
                [('student_id', '=', child.id)], limit=30,
            )
            total = len(lines)
            present = len(lines.filtered(lambda line: line.status == 'present'))
            pct = round((present / total) * 100, 1) if total else 0.0
            dues = request.env['edu.student.fee.due'].search(
                [('student_id', '=', child.id), ('state', '!=', 'paid')],
            )
            outstanding = sum(dues.mapped('balance_amount')) if dues else 0.0
            summaries.append({
                'student': child,
                'attendance_pct': pct,
                'outstanding': outstanding,
            })
        context = self._base_parent_context('home', 'Overview')
        context['summaries'] = summaries
        return request.render('edu_portal.parent_home_page', context)

    @http.route('/portal/parent/attendance', type='http', auth='user', website=False)
    def parent_attendance(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('attendance', 'Attendance')
        child = context['active_child']
        if child:
            context['lines'] = request.env['edu.attendance.sheet.line'].search(
                [('student_id', '=', child.id)], order='session_date desc', limit=200,
            )
        else:
            context['lines'] = []
        return request.render('edu_portal.parent_attendance_page', context)

    @http.route('/portal/parent/results', type='http', auth='user', website=False)
    def parent_results(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('results', 'Results')
        child = context['active_child']
        if child:
            context['marksheets'] = request.env['edu.exam.marksheet'].search(
                [('student_id', '=', child.id)], order='create_date desc',
            )
        else:
            context['marksheets'] = []
        return request.render('edu_portal.parent_results_page', context)

    @http.route('/portal/parent/assessments', type='http', auth='user', website=False)
    def parent_assessments(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('assessments', 'Assessments')
        child = context['active_child']
        if child:
            context['records'] = request.env['edu.continuous.assessment.record'].search(
                [('student_id', '=', child.id)], order='assessment_date desc', limit=200,
            )
        else:
            context['records'] = []
        return request.render('edu_portal.parent_assessments_page', context)

    @http.route('/portal/parent/fees', type='http', auth='user', website=False)
    def parent_fees(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('fees', 'Fees')
        child = context['active_child']
        if child:
            dues = request.env['edu.student.fee.due'].search(
                [('student_id', '=', child.id)], order='due_date',
            )
            payments = request.env['edu.student.payment'].search(
                [('student_id', '=', child.id)], order='payment_date desc',
            )
            context['dues'] = dues
            context['payments'] = payments
            context['total_due'] = sum(dues.mapped('balance_amount')) if dues else 0.0
        else:
            context['dues'] = []
            context['payments'] = []
            context['total_due'] = 0.0
        return request.render('edu_portal.parent_fees_page', context)

    @http.route('/portal/parent/profile', type='http', auth='user', website=False)
    def parent_profile(self, **kw):
        if not self._guard_parent():
            return request.redirect('/portal')
        context = self._base_parent_context('profile', 'My Profile')
        return request.render('edu_portal.parent_profile_page', context)
