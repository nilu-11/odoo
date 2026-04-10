"""Student portal controllers."""
from odoo import http
from odoo.http import request
from .helpers import base_context, get_student_record, get_portal_role


class StudentPortalController(http.Controller):

    def _guard_student(self):
        user = request.env.user
        if get_portal_role(user) != 'student':
            return None
        return get_student_record(user)

    def _student_sidebar_items(self, student, active=None):
        return [
            {'key': 'home',        'label': 'Dashboard',   'icon': '🏠', 'url': '/portal/student/home'},
            {'key': 'attendance',  'label': 'Attendance',  'icon': '✓', 'url': '/portal/student/attendance'},
            {'key': 'results',     'label': 'Results',     'icon': '📊', 'url': '/portal/student/results'},
            {'key': 'assessments', 'label': 'Assessments', 'icon': '📝', 'url': '/portal/student/assessments'},
            {'key': 'fees',        'label': 'Fees',        'icon': '💰', 'url': '/portal/student/fees'},
            {'key': 'profile',     'label': 'Profile',     'icon': '👤', 'url': '/portal/student/profile'},
        ]

    @http.route('/portal/student/home', type='http', auth='user', website=False)
    def student_home(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        lines = request.env['edu.attendance.sheet.line'].search(
            [('student_id', '=', student.id)], limit=30, order='session_date desc',
        )
        total = len(lines)
        present = len(lines.filtered(lambda line: line.status == 'present'))
        attendance_pct = round((present / total) * 100, 1) if total else 0.0
        marksheets = request.env['edu.exam.marksheet'].search(
            [('student_id', '=', student.id)], limit=5, order='create_date desc',
        )
        dues = request.env['edu.student.fee.due'].search(
            [('student_id', '=', student.id), ('state', '!=', 'paid')],
        )
        outstanding = sum(dues.mapped('balance_amount')) if dues else 0.0
        context = base_context(active_item='home', page_title='Dashboard')
        context.update({
            'student': student,
            'attendance_pct': attendance_pct,
            'recent_marksheets': marksheets,
            'outstanding_dues': outstanding,
            'sidebar_items': self._student_sidebar_items(student, 'home'),
        })
        return request.render('edu_portal.student_home_page', context)

    @http.route('/portal/student/attendance', type='http', auth='user', website=False)
    def student_attendance(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        lines = request.env['edu.attendance.sheet.line'].search(
            [('student_id', '=', student.id)], order='session_date desc', limit=200,
        )
        context = base_context(active_item='attendance', page_title='My Attendance')
        context.update({
            'student': student,
            'lines': lines,
            'sidebar_items': self._student_sidebar_items(student, 'attendance'),
        })
        return request.render('edu_portal.student_attendance_page', context)

    @http.route('/portal/student/results', type='http', auth='user', website=False)
    def student_results(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        marksheets = request.env['edu.exam.marksheet'].search(
            [('student_id', '=', student.id)], order='create_date desc',
        )
        context = base_context(active_item='results', page_title='My Results')
        context.update({
            'student': student,
            'marksheets': marksheets,
            'sidebar_items': self._student_sidebar_items(student, 'results'),
        })
        return request.render('edu_portal.student_results_page', context)

    @http.route('/portal/student/assessments', type='http', auth='user', website=False)
    def student_assessments(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        records = request.env['edu.continuous.assessment.record'].search(
            [('student_id', '=', student.id)], order='assessment_date desc', limit=200,
        )
        context = base_context(active_item='assessments', page_title='My Assessments')
        context.update({
            'student': student,
            'records': records,
            'sidebar_items': self._student_sidebar_items(student, 'assessments'),
        })
        return request.render('edu_portal.student_assessments_page', context)

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
        context = base_context(active_item='fees', page_title='My Fees')
        context.update({
            'student': student,
            'dues': dues,
            'payments': payments,
            'total_due': total_due,
            'sidebar_items': self._student_sidebar_items(student, 'fees'),
        })
        return request.render('edu_portal.student_fees_page', context)

    @http.route('/portal/student/profile', type='http', auth='user', website=False)
    def student_profile(self, **kw):
        student = self._guard_student()
        if not student:
            return request.redirect('/portal')
        context = base_context(active_item='profile', page_title='My Profile')
        context.update({
            'student': student,
            'sidebar_items': self._student_sidebar_items(student, 'profile'),
        })
        return request.render('edu_portal.student_profile_page', context)
