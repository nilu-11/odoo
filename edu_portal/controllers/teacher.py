"""Teacher portal controllers."""
from odoo import http, _
from odoo.http import request
from .helpers import (
    base_context, get_teacher_employee, teacher_owns_classroom, get_portal_role,
)


class TeacherPortalController(http.Controller):

    def _guard_teacher(self):
        """Ensure current user is a teacher. Returns employee or None."""
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        return get_teacher_employee(user)

    def _teacher_sidebar_items(self, employee, active=None):
        """Build sidebar navigation with badges for a teacher."""
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms_with_open = Classroom.search_count([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'active'),
        ])
        marks_entry_papers = ExamPaper.search_count([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ])
        items = [
            {'key': 'home',        'label': 'Dashboard',    'icon': '🏠', 'url': '/portal/teacher/home'},
            {'key': 'classrooms',  'label': 'Classrooms',   'icon': '📚', 'url': '/portal/teacher/classrooms',
             'badge': classrooms_with_open or None},
            {'key': 'marks',       'label': 'Exam Marks',   'icon': '📝', 'url': '/portal/teacher/marks',
             'badge': marks_entry_papers or None},
            {'key': 'assessments', 'label': 'Assessments',  'icon': '✅', 'url': '/portal/teacher/assessments'},
            {'key': 'profile',     'label': 'My Profile',   'icon': '👤', 'url': '/portal/teacher/profile'},
        ]
        return items

    # ─── Home (Dashboard) ───────────────────────────────────
    @http.route('/portal/teacher/home', type='http', auth='user', website=False)
    def teacher_home(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        Classroom = request.env['edu.classroom'].sudo()
        ExamPaper = request.env['edu.exam.paper'].sudo()
        classrooms = Classroom.search([('teacher_id', '=', employee.id)])
        # Build status info per classroom
        classroom_cards = []
        for cl in classrooms:
            marks_papers = ExamPaper.search_count([
                ('batch_id', '=', cl.batch_id.id),
                ('curriculum_line_id', '=', cl.curriculum_line_id.id),
                ('teacher_id', '=', employee.id),
                ('state', '=', 'marks_entry'),
            ])
            if marks_papers:
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
        context = base_context(active_item='home', page_title='Dashboard')
        context.update({
            'employee': employee,
            'classroom_cards': classroom_cards,
            'total_classrooms': len(classrooms),
            'total_students': sum(classrooms.mapped('student_count')),
            'pending_marks': ExamPaper.search_count([
                ('teacher_id', '=', employee.id), ('state', '=', 'marks_entry'),
            ]),
            'sidebar_items': self._teacher_sidebar_items(employee, 'home'),
        })
        return request.render('edu_portal.teacher_home_page', context)

    # ─── Classrooms List ────────────────────────────────────
    @http.route('/portal/teacher/classrooms', type='http', auth='user', website=False)
    def teacher_classrooms(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classrooms = request.env['edu.classroom'].sudo().search(
            [('teacher_id', '=', employee.id)],
        )
        context = base_context(active_item='classrooms', page_title='My Classrooms')
        context.update({
            'employee': employee,
            'classrooms': classrooms,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_classrooms_page', context)

    # ─── Classroom Detail ───────────────────────────────────
    @http.route('/portal/teacher/classroom/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_classroom_detail(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        # Get active students in this section
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        students = histories.mapped('student_id')
        context = base_context(
            active_item='classrooms',
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'students': students,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_classroom_detail_page', context)

    # ─── Profile ────────────────────────────────────────────
    @http.route('/portal/teacher/profile', type='http', auth='user', website=False)
    def teacher_profile(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        context = base_context(active_item='profile', page_title='My Profile')
        context.update({
            'employee': employee,
            'sidebar_items': self._teacher_sidebar_items(employee, 'profile'),
        })
        return request.render('edu_portal.teacher_profile_page', context)

    # ─── Attendance ─────────────────────────────────────────
    @http.route('/portal/teacher/attendance/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_attendance(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        # Get or create today's attendance sheet
        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        register = classroom.attendance_register_id
        if not register:
            classroom._ensure_attendance_register()
            register = classroom.attendance_register_id
        # Find an in-progress or draft sheet, else get the latest
        sheet = AttendanceSheet.search([
            ('register_id', '=', register.id),
            ('state', 'in', ['draft', 'in_progress']),
        ], order='session_date desc', limit=1)
        context = base_context(
            active_item='classrooms',
            page_title='Attendance · %s' % classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'sheet': sheet,
            'sidebar_items': self._teacher_sidebar_items(employee, 'classrooms'),
        })
        return request.render('edu_portal.teacher_attendance_page', context)

    @http.route('/portal/teacher/attendance/mark', type='http', auth='user', methods=['POST'], website=False, csrf=False)
    def teacher_attendance_mark(self, line_id, status, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.not_found()
        line = request.env['edu.attendance.sheet.line'].sudo().browse(int(line_id))
        if not line.exists():
            return request.not_found()
        classroom = line.classroom_id
        if not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        if status not in ('present', 'absent', 'late', 'excused'):
            return request.not_found()
        line.write({'status': status})
        # Return the updated row
        return request.render('edu_portal.teacher_attendance_row_partial', {
            'line': line,
        })

    # ─── Marks Entry ────────────────────────────────────────
    @http.route('/portal/teacher/marks', type='http', auth='user', website=False)
    def teacher_marks_list(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        papers = request.env['edu.exam.paper'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('state', '=', 'marks_entry'),
        ])
        context = base_context(active_item='marks', page_title='Marks Entry')
        context.update({
            'employee': employee,
            'papers': papers,
            'sidebar_items': self._teacher_sidebar_items(employee, 'marks'),
        })
        return request.render('edu_portal.teacher_marks_list_page', context)

    @http.route('/portal/teacher/marks/<int:paper_id>', type='http', auth='user', website=False)
    def teacher_marks_entry(self, paper_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        paper = request.env['edu.exam.paper'].sudo().browse(paper_id)
        if not paper.exists() or paper.teacher_id != employee:
            return request.not_found()
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('exam_paper_id', '=', paper.id),
            ('is_latest_attempt', '=', True),
        ])
        context = base_context(active_item='marks', page_title='Marks · %s' % paper.display_name)
        context.update({
            'employee': employee,
            'paper': paper,
            'marksheets': marksheets,
            'sidebar_items': self._teacher_sidebar_items(employee, 'marks'),
        })
        return request.render('edu_portal.teacher_marks_entry_page', context)

    @http.route('/portal/teacher/marks/save', type='http', auth='user', methods=['POST'], website=False, csrf=False)
    def teacher_marks_save(self, marksheet_id, marks_obtained, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.not_found()
        marksheet = request.env['edu.exam.marksheet'].sudo().browse(int(marksheet_id))
        if not marksheet.exists() or marksheet.exam_paper_id.teacher_id != employee:
            return request.not_found()
        try:
            marks_value = float(marks_obtained) if marks_obtained else 0.0
        except (TypeError, ValueError):
            return request.not_found()
        if marks_value < 0 or marks_value > marksheet.max_marks:
            return request.render('edu_portal.teacher_marks_row_partial', {
                'marksheet': marksheet,
                'error': 'Invalid marks: must be between 0 and %s' % marksheet.max_marks,
            })
        marksheet.write({'marks_obtained': marks_value})
        return request.render('edu_portal.teacher_marks_row_partial', {
            'marksheet': marksheet,
            'error': None,
        })

    # ─── Assessments ────────────────────────────────────────
    @http.route('/portal/teacher/assessments', type='http', auth='user', website=False)
    def teacher_assessments_list(self, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classrooms = request.env['edu.classroom'].sudo().search(
            [('teacher_id', '=', employee.id)],
        )
        context = base_context(active_item='assessments', page_title='Assessments')
        context.update({
            'employee': employee,
            'classrooms': classrooms,
            'sidebar_items': self._teacher_sidebar_items(employee, 'assessments'),
        })
        return request.render('edu_portal.teacher_assessments_list_page', context)

    @http.route('/portal/teacher/assessments/<int:classroom_id>', type='http', auth='user', website=False)
    def teacher_classroom_assessments(self, classroom_id, **kw):
        employee = self._guard_teacher()
        if not employee:
            return request.redirect('/portal')
        classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
        if not classroom.exists() or not teacher_owns_classroom(employee, classroom):
            return request.not_found()
        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc', limit=100)
        context = base_context(
            active_item='assessments',
            page_title='Assessments · %s' % classroom.name,
        )
        context.update({
            'employee': employee,
            'classroom': classroom,
            'records': records,
            'sidebar_items': self._teacher_sidebar_items(employee, 'assessments'),
        })
        return request.render('edu_portal.teacher_classroom_assessments_page', context)
