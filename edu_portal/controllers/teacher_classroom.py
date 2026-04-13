"""Teacher in-classroom hub controllers.

Owns every ``/portal/teacher/classroom/<int:classroom_id>/<tab>`` route.
Each handler:

1. Calls ``guard_classroom_access(classroom_id, 'teacher')`` as its
   first line — returns 404 if the user doesn't own the classroom.
2. Calls ``build_portal_context(...)`` to get the shared context with
   registry-resolved sidebar items and classroom tabs.
3. Loads per-tab data and merges it in.
4. Renders the role-specific template.

The 6 built-in tabs are: stream, attendance, exams, assessments,
results, people. Tabs not yet implemented render a "coming soon"
placeholder via the shared empty_state_component.
"""
from odoo import http
from odoo.http import request

from .helpers import (
    build_portal_context,
    get_portal_role,
    get_teacher_employee,
    guard_classroom_access,
)


class TeacherClassroomController(http.Controller):

    # ─── Auth plumbing ─────────────────────────────────────────

    def _guard(self, classroom_id):
        """Return (classroom, employee) or None if unauthorised."""
        user = request.env.user
        if get_portal_role(user) != 'teacher':
            return None
        classroom = guard_classroom_access(classroom_id, 'teacher')
        if not classroom:
            return None
        employee = get_teacher_employee(user)
        return classroom, employee

    # ─── Entry point: /portal/teacher/classroom/<id> → stream ──

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_index(self, classroom_id, **kw):
        """Bare classroom URL redirects to the default tab (stream)."""
        return request.redirect(f'/portal/teacher/classroom/{classroom_id}/stream')

    # ─── Tab: Stream ───────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/stream',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_stream(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        posts = request.env['edu.classroom.post'].sudo().search([
            ('classroom_id', '=', classroom.id),
            ('active', '=', True),
        ])  # order baked into the model: pinned desc, posted_at desc
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='stream',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'posts': posts,
        })
        return request.render('edu_portal.teacher_classroom_stream_page', context)

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/stream/post',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_stream_create(self, classroom_id, body, pinned=None, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, _employee = guard
        if not (body or '').strip():
            return request.redirect(f'/portal/teacher/classroom/{classroom.id}/stream')
        request.env['edu.classroom.post'].sudo().create({
            'classroom_id': classroom.id,
            'author_id': request.env.user.id,
            'body': body,
            'pinned': bool(pinned),
        })
        return request.redirect(f'/portal/teacher/classroom/{classroom.id}/stream')

    @http.route(
        '/portal/teacher/classroom/stream/pin/<int:post_id>',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_stream_pin(self, post_id, **kw):
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        employee = get_teacher_employee(request.env.user)
        if not employee:
            return request.not_found()
        post = request.env['edu.classroom.post'].sudo().browse(post_id)
        if not post.exists():
            return request.not_found()
        if post.classroom_id.teacher_id != employee:
            return request.not_found()
        post.action_toggle_pin()
        return request.redirect(
            f'/portal/teacher/classroom/{post.classroom_id.id}/stream'
        )

    @http.route(
        '/portal/teacher/classroom/stream/archive/<int:post_id>',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_stream_archive(self, post_id, **kw):
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        employee = get_teacher_employee(request.env.user)
        if not employee:
            return request.not_found()
        post = request.env['edu.classroom.post'].sudo().browse(post_id)
        if not post.exists():
            return request.not_found()
        if post.classroom_id.teacher_id != employee:
            return request.not_found()
        classroom_id = post.classroom_id.id
        post.action_archive_post()
        return request.redirect(
            f'/portal/teacher/classroom/{classroom_id}/stream'
        )

    # ─── Tab: Attendance ───────────────────────────────────────

    def _get_or_create_register(self, classroom):
        register = classroom.attendance_register_id
        if not register:
            classroom._ensure_attendance_register()
            register = classroom.attendance_register_id
        return register

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_attendance(self, classroom_id, sheet_id=None, **kw):
        """Dashboard + optional modal editor for a selected sheet."""
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        register = self._get_or_create_register(classroom)

        history = AttendanceSheet.search(
            [('register_id', '=', register.id)],
            order='session_date desc, time_from desc',
            limit=50,
        )

        sheet = AttendanceSheet
        if sheet_id:
            try:
                candidate = AttendanceSheet.browse(int(sheet_id))
                if candidate.exists() and candidate.register_id == register:
                    sheet = candidate
            except (TypeError, ValueError):
                pass
        if not sheet:
            sheet = history.filtered(
                lambda s: s.state in ('draft', 'in_progress')
            )[:1]

        # Ensure lines exist for an open sheet so the teacher can mark.
        if sheet and sheet.state == 'draft' and not sheet.line_ids:
            sheet.action_start()

        # ── Dashboard stats ──────────────────────────────────────
        from datetime import date
        today = date.today()

        total_students = len(sheet.line_ids) if sheet else 0
        if not total_students:
            ProgHistory = request.env['edu.student.progression.history'].sudo()
            total_students = ProgHistory.search_count([
                ('section_id', '=', classroom.section_id.id),
                ('state', '=', 'active'),
            ])

        submitted = history.filtered(lambda s: s.state == 'submitted')
        sessions_count = len(submitted)
        if submitted:
            total_lines = sum(s.line_count for s in submitted)
            total_present = sum(s.present_count for s in submitted)
            avg_rate = round(total_present / total_lines * 100) if total_lines else 0
        else:
            avg_rate = 0

        today_sheet = history.filtered(lambda s: s.session_date == today)[:1]

        # Sort lines for display
        sorted_lines = []
        if sheet and sheet.line_ids:
            sorted_lines = sheet.line_ids.sorted(
                key=lambda l: (l.roll_number or '', l.student_id.display_name)
            )

        auto_open = kw.get('modal') == '1' and sheet and sheet.state == 'in_progress'

        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='attendance',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'sheet': sheet,
            'sorted_lines': sorted_lines,
            'history': history,
            'register': register,
            'today_str': today.isoformat(),
            'total_students': total_students,
            'sessions_count': sessions_count,
            'avg_rate': avg_rate,
            'today_sheet': today_sheet,
            'auto_open_modal': auto_open,
        })
        return request.render('edu_portal.teacher_classroom_attendance_page', context)

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance/create',
        type='http', auth='user', methods=['POST'], website=False, csrf=False,
    )
    def teacher_classroom_attendance_create(
        self, classroom_id, session_date=None, **kw
    ):
        """Create a new attendance sheet, then redirect with modal auto-open."""
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, _employee = guard
        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        register = self._get_or_create_register(classroom)

        from datetime import date as _date
        try:
            target = (
                _date.fromisoformat(session_date) if session_date else _date.today()
            )
        except ValueError:
            target = _date.today()

        existing = AttendanceSheet.search([
            ('register_id', '=', register.id),
            ('session_date', '=', target),
        ], limit=1)
        if existing:
            sheet = existing
        else:
            sheet = AttendanceSheet.create({
                'register_id': register.id,
                'session_date': target,
            })
            try:
                sheet.action_start()
            except Exception:
                pass
        return request.redirect(
            f'/portal/teacher/classroom/{classroom_id}/attendance'
            f'?sheet_id={sheet.id}&modal=1'
        )

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance/<int:sheet_id>/submit',
        type='http', auth='user', methods=['POST'], website=False, csrf=False,
    )
    def teacher_classroom_attendance_submit(self, classroom_id, sheet_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, _employee = guard
        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if not sheet.exists() or sheet.classroom_id != classroom:
            return request.not_found()
        if sheet.state == 'in_progress':
            try:
                sheet.action_submit()
            except Exception:
                pass
        return request.redirect(
            f'/portal/teacher/classroom/{classroom_id}/attendance'
            f'?sheet_id={sheet.id}'
        )

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance/<int:sheet_id>/mark-all',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_attendance_mark_all(
        self, classroom_id, sheet_id, status, **kw
    ):
        """Bulk-mark all lines on a sheet. Returns HTMX fragment."""
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, _employee = guard
        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if (not sheet.exists() or sheet.classroom_id != classroom
                or sheet.state != 'in_progress'):
            return request.not_found()
        if status not in ('present', 'absent', 'late', 'excused'):
            return request.not_found()
        sheet.line_ids.write({'status': status})
        sorted_lines = sheet.line_ids.sorted(
            key=lambda l: (l.roll_number or '', l.student_id.display_name)
        )
        return request.render('edu_portal.teacher_attendance_modal_rows', {
            'sorted_lines': sorted_lines,
            'sheet': sheet,
        })

    @http.route(
        '/portal/teacher/classroom/attendance/mark',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_attendance_mark(self, line_id, status, **kw):
        """HTMX row update — auth-checked via the line's parent classroom."""
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        line = request.env['edu.attendance.sheet.line'].sudo().browse(int(line_id))
        if not line.exists():
            return request.not_found()
        classroom = line.classroom_id
        if not guard_classroom_access(classroom.id, 'teacher'):
            return request.not_found()
        if status not in ('present', 'absent', 'late', 'excused'):
            return request.not_found()
        line.write({'status': status})
        return request.render('edu_portal.teacher_attendance_row_partial', {
            'line': line,
        })

    # ─── Attendance matrix report ────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/attendance/matrix',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_attendance_matrix(
        self, classroom_id, date_from=None, date_to=None, **kw
    ):
        """Student × Date attendance matrix with date-range filter."""
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        register = self._get_or_create_register(classroom)

        from datetime import date as _date, timedelta
        today = _date.today()
        try:
            d_from = _date.fromisoformat(date_from) if date_from else None
        except ValueError:
            d_from = None
        try:
            d_to = _date.fromisoformat(date_to) if date_to else None
        except ValueError:
            d_to = None

        # Default: last 30 days
        if not d_to:
            d_to = today
        if not d_from:
            d_from = d_to - timedelta(days=29)

        AttendanceSheet = request.env['edu.attendance.sheet'].sudo()
        sheets = AttendanceSheet.search([
            ('register_id', '=', register.id),
            ('session_date', '>=', d_from),
            ('session_date', '<=', d_to),
            ('state', '=', 'submitted'),
        ], order='session_date asc')

        # Build date columns (sorted dates with submitted sheets)
        date_cols = [s.session_date for s in sheets]

        # Build student rows: {student_id: {date: status, ...}}
        # Collect unique students from all sheet lines
        all_lines = request.env['edu.attendance.sheet.line'].sudo().search([
            ('sheet_id', 'in', sheets.ids),
        ])

        student_map = {}  # student record → {date → status}
        for ln in all_lines:
            st = ln.student_id
            if st.id not in student_map:
                student_map[st.id] = {'student': st, 'dates': {}, 'present': 0, 'total': 0}
            entry = student_map[st.id]
            entry['dates'][ln.sheet_id.session_date] = ln.status
            entry['total'] += 1
            if ln.status in ('present', 'late'):
                entry['present'] += 1

        # Sort students by name
        matrix_rows = sorted(
            student_map.values(),
            key=lambda r: (r['student'].roll_number or '', r['student'].display_name),
        )

        # Calculate per-student percentage
        for row in matrix_rows:
            row['pct'] = round(row['present'] / row['total'] * 100) if row['total'] else 0

        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='attendance',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'date_cols': date_cols,
            'matrix_rows': matrix_rows,
            'date_from': d_from.isoformat(),
            'date_to': d_to.isoformat(),
            'total_sessions': len(sheets),
        })
        return request.render(
            'edu_portal.teacher_classroom_attendance_matrix_page', context,
        )

    # ─── Tab: Exams ────────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/exams',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_exams(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        ExamPaper = request.env['edu.exam.paper'].sudo()
        papers = ExamPaper.search([
            ('batch_id', '=', classroom.batch_id.id),
            ('curriculum_line_id', '=', classroom.curriculum_line_id.id),
        ], order='create_date desc')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='exams',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'papers': papers,
        })
        return request.render('edu_portal.teacher_classroom_exams_page', context)

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/exams/<int:paper_id>',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_exam_marks(self, classroom_id, paper_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        paper = request.env['edu.exam.paper'].sudo().browse(paper_id)
        if not paper.exists() or paper.batch_id != classroom.batch_id \
                or paper.curriculum_line_id != classroom.curriculum_line_id:
            return request.not_found()
        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('exam_paper_id', '=', paper.id),
            ('section_id', '=', classroom.section_id.id),
            ('is_latest_attempt', '=', True),
        ])
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='exams',
            classroom=classroom,
            page_title=f'{classroom.name} — {paper.display_name}',
        )
        context.update({
            'employee': employee,
            'paper': paper,
            'marksheets': marksheets,
        })
        return request.render('edu_portal.teacher_classroom_exam_marks_page', context)

    @http.route(
        '/portal/teacher/classroom/exams/save',
        type='http', auth='user', methods=['POST'],
        website=False, csrf=False,
    )
    def teacher_classroom_exam_save(self, marksheet_id, marks_obtained, **kw):
        if get_portal_role(request.env.user) != 'teacher':
            return request.not_found()
        employee = get_teacher_employee(request.env.user)
        if not employee:
            return request.not_found()
        marksheet = request.env['edu.exam.marksheet'].sudo().browse(int(marksheet_id))
        if not marksheet.exists():
            return request.not_found()
        # Verify the teacher owns a classroom matching this paper's batch/curriculum
        classroom = request.env['edu.classroom'].sudo().search([
            ('teacher_id', '=', employee.id),
            ('batch_id', '=', marksheet.exam_paper_id.batch_id.id),
            ('curriculum_line_id', '=', marksheet.exam_paper_id.curriculum_line_id.id),
            ('section_id', '=', marksheet.section_id.id),
        ], limit=1)
        if not classroom:
            return request.not_found()
        try:
            marks_value = float(marks_obtained) if marks_obtained else 0.0
        except (TypeError, ValueError):
            return request.not_found()
        if marks_value < 0 or marks_value > marksheet.max_marks:
            return request.render('edu_portal.teacher_marks_row_partial', {
                'marksheet': marksheet,
                'error': f'Invalid marks: must be between 0 and {marksheet.max_marks}',
            })
        marksheet.write({'marks_obtained': marks_value})
        return request.render('edu_portal.teacher_marks_row_partial', {
            'marksheet': marksheet,
            'error': None,
        })

    # ─── Tab: Assessments ──────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/assessments',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_assessments(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc', limit=100)
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='assessments',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'records': records,
        })
        return request.render('edu_portal.teacher_classroom_assessments_page', context)

    # ─── Tab: Results ──────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/results',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_results(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        # Published student results scoped to this section + term
        ResultStudent = request.env['edu.result.student'].sudo()
        results = ResultStudent.search([
            ('section_id', '=', classroom.section_id.id),
            ('program_term_id', '=', classroom.program_term_id.id),
            ('result_session_id.state', 'in', ('published', 'closed')),
        ], order='student_id')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='results',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'results': results,
        })
        return request.render('edu_portal.teacher_classroom_results_page', context)

    # ─── Tab: People ───────────────────────────────────────────

    @http.route(
        '/portal/teacher/classroom/<int:classroom_id>/people',
        type='http', auth='user', website=False,
    )
    def teacher_classroom_people(self, classroom_id, **kw):
        guard = self._guard(classroom_id)
        if not guard:
            return request.not_found()
        classroom, employee = guard
        histories = request.env['edu.student.progression.history'].sudo().search([
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ])
        students = histories.mapped('student_id')
        context = build_portal_context(
            active_sidebar_key='home',
            active_tab_key='people',
            classroom=classroom,
            page_title=classroom.name,
        )
        context.update({
            'employee': employee,
            'students': students,
        })
        return request.render('edu_portal.teacher_classroom_people_page', context)
