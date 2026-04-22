import logging
from datetime import date

from odoo import http, fields as odoo_fields
from odoo.http import request
from odoo.exceptions import UserError

from .helpers import (
    get_portal_role,
    get_teacher_employee,
    guard_classroom_access,
    build_portal_context,
    get_section_students,
)

_logger = logging.getLogger(__name__)


class EduPortalTeacherClassroom(http.Controller):
    """Teacher in-classroom portal routes (6 tabs)."""

    # ── Common guard ───────────────────────────────────────────────────────

    def _guard(self, classroom_id):
        """Return (classroom, employee, error) tuple."""
        user = request.env.user
        role = get_portal_role(user)
        if role != 'teacher':
            return None, None, request.redirect('/portal')
        employee = get_teacher_employee(user)
        if not employee:
            return None, None, request.redirect('/portal')
        classroom = guard_classroom_access(classroom_id, 'teacher')
        if not classroom:
            return None, None, request.not_found()
        return classroom, employee, None

    # ══════════════════════════════════════════════════════════════════════
    # Root redirect
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>', type='http',
                auth='user', website=False)
    def teacher_classroom_root(self, classroom_id, **kw):
        return request.redirect(
            '/portal/teacher/classroom/%d/stream' % classroom_id
        )

    # ══════════════════════════════════════════════════════════════════════
    # Tab 1: Stream
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/stream',
                type='http', auth='user', website=False)
    def teacher_classroom_stream(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        posts = request.env['edu.classroom.post'].sudo().search([
            ('classroom_id', '=', classroom.id),
            ('active', '=', True),
        ], order='pinned desc, posted_at desc')

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='stream',
            active_sidebar_key='courses',
            page_title=classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Stream'],
            posts=posts,
        )
        return request.render('edu_portal.teacher_classroom_stream', ctx)

    @http.route('/portal/teacher/classroom/<int:classroom_id>/stream/post',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_stream_post(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        body = kw.get('body', '').strip()
        if body:
            request.env['edu.classroom.post'].sudo().create({
                'classroom_id': classroom.id,
                'author_id': request.env.user.id,
                'body': body,
            })

        return request.redirect(
            '/portal/teacher/classroom/%d/stream' % classroom_id
        )

    @http.route('/portal/teacher/classroom/<int:classroom_id>/stream/pin/<int:post_id>',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_stream_pin(self, classroom_id, post_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        post = request.env['edu.classroom.post'].sudo().browse(post_id)
        if post.exists() and post.classroom_id.id == classroom.id:
            post.action_toggle_pin()

        return request.redirect(
            '/portal/teacher/classroom/%d/stream' % classroom_id
        )

    @http.route('/portal/teacher/classroom/<int:classroom_id>/stream/archive/<int:post_id>',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_stream_archive(self, classroom_id, post_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        post = request.env['edu.classroom.post'].sudo().browse(post_id)
        if post.exists() and post.classroom_id.id == classroom.id:
            post.action_archive_post()

        return request.redirect(
            '/portal/teacher/classroom/%d/stream' % classroom_id
        )

    # ══════════════════════════════════════════════════════════════════════
    # Tab 2: Attendance
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance',
                type='http', auth='user', website=False)
    def teacher_classroom_attendance(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        register = getattr(classroom, 'attendance_register_id', False)
        sheets_orm = request.env['edu.attendance.sheet'].sudo()
        attendance_summary = {}

        if register:
            sheets_orm = request.env['edu.attendance.sheet'].sudo().search([
                ('register_id', '=', register.id),
            ], order='session_date desc, time_from desc')
            try:
                attendance_summary = register.get_student_attendance_summary()
            except Exception:
                _logger.warning(
                    'Could not compute attendance summary for register %s',
                    register.id, exc_info=True,
                )

        # Build attendance_sheets dicts for template
        attendance_sheets = []
        for sh in sheets_orm:
            total = len(sh.line_ids) if hasattr(sh, 'line_ids') else 0
            present = len(sh.line_ids.filtered(lambda l: l.status == 'present')) if total else 0
            rate = round(present * 100 / total) if total else 0
            attendance_sheets.append({
                'id': sh.id,
                'date': str(sh.session_date) if sh.session_date else '',
                'time': '%s–%s' % (
                    '{:.0f}:{:02.0f}'.format(*divmod(sh.time_from * 60, 60)) if hasattr(sh, 'time_from') and sh.time_from else '',
                    '{:.0f}:{:02.0f}'.format(*divmod(sh.time_to * 60, 60)) if hasattr(sh, 'time_to') and sh.time_to else '',
                ) if hasattr(sh, 'time_from') else '',
                'state': sh.state or '',
                'present': present,
                'total': total,
                'rate': rate,
            })

        # Find the latest in-progress sheet and build student roster
        active_sheet = None
        roster = []
        active_sheet_id = None
        for sh in sheets_orm:
            if sh.state in ('draft', 'in_progress'):
                active_sheet = sh
                active_sheet_id = sh.id
                break

        if active_sheet:
            students = get_section_students(classroom.section_id)
            # Map existing lines by student_id
            line_map = {}
            if hasattr(active_sheet, 'line_ids'):
                for line in active_sheet.line_ids:
                    line_map[line.student_id.id] = line.status or ''

            for idx, s in enumerate(students):
                name = s.partner_id.name if s.partner_id else (s.display_name or '')
                words = [w for w in name.split() if w]
                initials = (''.join(w[0] for w in words[:2])).upper() or '?'
                roster.append({
                    'id': s.id,
                    'name': name,
                    'initials': initials,
                    'hue': (idx * 47) % 360,
                    'student_no': s.student_no or '',
                    'status': line_map.get(s.id, ''),
                })

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='attendance',
            active_sidebar_key='courses',
            page_title='%s - Attendance' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Attendance'],
            attendance_sheets=attendance_sheets,
            roster=roster,
            active_sheet_id=active_sheet_id,
            attendance_summary=attendance_summary,
        )
        return request.render('edu_portal.teacher_classroom_attendance', ctx)

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance/create',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_attendance_create(self, classroom_id, **kw):
        """Create a new attendance sheet for today and redirect to attendance tab."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        register = getattr(classroom, 'attendance_register_id', False)
        if not register:
            return request.redirect(
                '/portal/teacher/classroom/%d/attendance' % classroom_id
            )

        today = date.today()
        # Check for existing sheet today
        existing = request.env['edu.attendance.sheet'].sudo().search([
            ('register_id', '=', register.id),
            ('session_date', '=', today),
        ], limit=1)

        target_sheet = existing
        if not existing:
            try:
                target_sheet = request.env['edu.attendance.sheet'].sudo().create({
                    'register_id': register.id,
                    'session_date': today,
                    'taken_by': request.env.user.id,
                })
                target_sheet.action_start()
            except (UserError, Exception) as e:
                _logger.warning(
                    'Could not create attendance sheet: %s', e,
                )
                return request.redirect(
                    '/portal/teacher/classroom/%d/attendance' % classroom_id
                )

        if target_sheet:
            return request.redirect(
                '/portal/teacher/classroom/%d/attendance/%d' % (classroom_id, target_sheet.id)
            )
        return request.redirect(
            '/portal/teacher/classroom/%d/attendance' % classroom_id
        )

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance/<int:sheet_id>',
                type='http', auth='user', website=False)
    def teacher_classroom_attendance_sheet(self, classroom_id, sheet_id, **kw):
        """Full attendance marking page with roster/photo/kiosk views."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if not sheet.exists():
            return request.redirect(
                '/portal/teacher/classroom/%d/attendance' % classroom_id
            )

        variant = kw.get('view', 'roster')
        if variant not in ('roster', 'photo', 'kiosk'):
            variant = 'roster'

        # Build student rows
        students = get_section_students(classroom.section_id)
        line_map = {}
        if hasattr(sheet, 'line_ids'):
            for line in sheet.line_ids:
                line_map[line.student_id.id] = line.status or ''

        attendance_students = []
        counts = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'unmarked': 0}
        for idx, s in enumerate(students):
            name = s.partner_id.name if s.partner_id else (s.display_name or '')
            words = [w for w in name.split() if w]
            initials = (''.join(w[0] for w in words[:2])).upper() or '?'
            status = line_map.get(s.id, '')
            status_short = {'present': 'p', 'absent': 'a', 'late': 'l', 'excused': 'e'}.get(status, '')
            if status in counts:
                counts[status] += 1
            else:
                counts['unmarked'] += 1
            attendance_students.append({
                'id': s.id,
                'name': name,
                'initials': initials,
                'hue': (idx * 47) % 360,
                'student_id': s.student_no or '',
                'id_short': (s.student_no or '')[-6:],
                'status': status_short,
                'attendance_rate': 100,
                'low_attendance': False,
                'at_risk': False,
            })

        total = len(attendance_students)
        kiosk_current = attendance_students[0] if attendance_students else None

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='attendance',
            active_sidebar_key='courses',
            page_title='%s - Attendance' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Attendance', 'Sheet #%d' % sheet.id],
            attendance_variant=variant,
            attendance_students=attendance_students,
            attendance_course_code=classroom.code or '',
            attendance_course_title=classroom.name or '',
            attendance_room='',
            attendance_time='',
            today_date_label=date.today().strftime('%A, %B %-d %Y'),
            sheet_number=sheet.id,
            sheet_state=sheet.state or 'draft',
            sheet_id=sheet.id,
            total_students=total,
            present_count=counts['present'],
            absent_count=counts['absent'],
            late_count=counts['late'],
            excused_count=counts['excused'],
            unmarked_count=counts['unmarked'],
            kiosk_current=kiosk_current,
        )
        return request.render('edu_portal.teacher_attendance', ctx)

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance/<int:sheet_id>/submit',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_attendance_submit(self, classroom_id, sheet_id, **kw):
        """Submit an in-progress attendance sheet."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if sheet.exists() and sheet.classroom_id.id == classroom.id:
            try:
                sheet.action_submit()
            except UserError as e:
                _logger.warning('Could not submit sheet: %s', e)

        return request.redirect(
            '/portal/teacher/classroom/%d/attendance' % classroom_id
        )

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance/<int:sheet_id>/mark-all',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_attendance_mark_all(self, classroom_id, sheet_id, **kw):
        """Bulk mark all students with a given status."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if not sheet.exists() or sheet.classroom_id.id != classroom.id:
            return request.redirect(
                '/portal/teacher/classroom/%d/attendance' % classroom_id
            )

        status = kw.get('status', 'present')
        if status not in ('present', 'absent', 'late', 'excused'):
            status = 'present'

        try:
            if status == 'present':
                sheet.action_mark_all_present()
            elif status == 'absent':
                sheet.action_mark_all_absent()
            elif status == 'late':
                sheet.action_mark_all_late()
            else:
                # 'excused' — set all lines individually
                if sheet.state == 'draft':
                    sheet.action_start()
                sheet.line_ids.write({'status': 'excused'})
        except UserError as e:
            _logger.warning('Bulk mark failed: %s', e)

        return request.redirect(
            '/portal/teacher/classroom/%d/attendance' % classroom_id
        )

    @http.route('/portal/teacher/classroom/<int:classroom_id>/attendance/mark',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_attendance_mark(self, classroom_id, **kw):
        """Mark a single student's attendance on a sheet."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return request.redirect('/portal/teacher/classroom/%d/attendance' % classroom_id)

        sheet_id = int(kw.get('sheet_id', 0))
        student_id = int(kw.get('student_id', 0))
        raw_status = kw.get('status', 'present')
        # Accept both short codes (p/a/l/e) and full names
        status_map = {'p': 'present', 'a': 'absent', 'l': 'late', 'e': 'excused'}
        status = status_map.get(raw_status, raw_status)
        if status not in ('present', 'absent', 'late', 'excused'):
            status = 'present'

        sheet = request.env['edu.attendance.sheet'].sudo().browse(sheet_id)
        if not sheet.exists():
            return request.redirect('/portal/teacher/classroom/%d/attendance' % classroom_id)

        # Start the sheet if still in draft
        if sheet.state == 'draft':
            try:
                sheet.action_start()
            except Exception:
                pass

        # Find existing line or create one
        line = request.env['edu.attendance.sheet.line'].sudo().search([
            ('sheet_id', '=', sheet.id),
            ('student_id', '=', student_id),
        ], limit=1)

        if line:
            try:
                line.write({'status': status})
            except UserError as e:
                _logger.warning('Mark attendance line failed: %s', e)
        elif student_id:
            try:
                request.env['edu.attendance.sheet.line'].sudo().create({
                    'sheet_id': sheet.id,
                    'student_id': student_id,
                    'status': status,
                })
            except Exception as e:
                _logger.warning('Create attendance line failed: %s', e)

        # AJAX requests get a simple text response; normal requests redirect
        if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return 'ok'
        return request.redirect(
            '/portal/teacher/classroom/%d/attendance/%d' % (classroom_id, sheet_id)
        )

    # ══════════════════════════════════════════════════════════════════════
    # Tab 3: Exams
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/exams',
                type='http', auth='user', website=False)
    def teacher_classroom_exams(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        papers = request.env['edu.exam.paper'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='exam_date desc, subject_id')

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='exams',
            active_sidebar_key='courses',
            page_title='%s - Exams' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Exams'],
            papers=papers,
        )
        return request.render('edu_portal.teacher_classroom_exams', ctx)

    @http.route('/portal/teacher/classroom/<int:classroom_id>/exams/<int:paper_id>',
                type='http', auth='user', website=False)
    def teacher_classroom_exam_marks(self, classroom_id, paper_id, **kw):
        """View / enter marks for a specific exam paper."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        paper = request.env['edu.exam.paper'].sudo().browse(paper_id)
        if not paper.exists() or paper.classroom_id.id != classroom.id:
            return request.not_found()

        marksheets = request.env['edu.exam.marksheet'].sudo().search([
            ('exam_paper_id', '=', paper.id),
            ('is_latest_attempt', '=', True),
        ], order='student_id')

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='exams',
            active_sidebar_key='courses',
            page_title='%s - %s' % (classroom.name, paper.display_name),
            crumbs=['Kopila', 'Courses', classroom.name, 'Exams',
                    paper.subject_id.name or 'Paper'],
            paper=paper,
            marksheets=marksheets,
        )
        return request.render('edu_portal.teacher_classroom_exam_marks', ctx)

    @http.route('/portal/teacher/classroom/<int:classroom_id>/exams/save',
                type='http', auth='user', website=False, methods=['POST'],
                csrf=True)
    def teacher_classroom_exam_save(self, classroom_id, **kw):
        """Save a single marksheet mark via HTMX. Returns HTML fragment."""
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return ''

        marksheet_id = int(kw.get('marksheet_id', 0))
        raw_marks = kw.get('raw_marks', '')

        marksheet = request.env['edu.exam.marksheet'].sudo().browse(marksheet_id)
        if not marksheet.exists():
            return '<span class="text-danger">Not found</span>'

        # Verify marksheet belongs to a paper in this classroom
        if marksheet.exam_paper_id.classroom_id.id != classroom.id:
            return '<span class="text-danger">Unauthorized</span>'

        # Check paper is in marks_entry state
        if marksheet.exam_paper_id.state != 'marks_entry':
            return '<span class="text-muted">Locked</span>'

        try:
            marks_val = float(raw_marks)
        except (ValueError, TypeError):
            return '<span class="text-danger">Invalid</span>'

        try:
            marksheet.write({
                'raw_marks': marks_val,
                'entered_by': request.env.user.id,
                'entered_on': odoo_fields.Datetime.now(),
            })
        except (UserError, Exception) as e:
            _logger.warning('Save marks failed: %s', e)
            return '<span class="text-danger">Error</span>'

        # Return updated fragment
        is_pass = marksheet.is_pass
        badge_class = 'bg-success' if is_pass else 'bg-danger'
        return (
            '<span class="badge %s">%.1f / %.1f</span>'
            % (badge_class, marksheet.final_marks, marksheet.max_marks)
        )

    # ══════════════════════════════════════════════════════════════════════
    # Tab 4: Assessments
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/assessments',
                type='http', auth='user', website=False)
    def teacher_classroom_assessments(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        records = request.env['edu.continuous.assessment.record'].sudo().search([
            ('classroom_id', '=', classroom.id),
        ], order='assessment_date desc, student_id')

        # Group by category for display
        categories = {}
        for rec in records:
            cat_name = rec.category_id.name or 'Uncategorized'
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(rec)

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='assessments',
            active_sidebar_key='courses',
            page_title='%s - Assessments' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Assessments'],
            records=records,
            categories=categories,
        )
        return request.render('edu_portal.teacher_classroom_assessments', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 5: Results
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/results',
                type='http', auth='user', website=False)
    def teacher_classroom_results(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        # Find published result sessions scoped to this classroom's batch/term
        result_sessions = request.env['edu.result.session'].sudo().search([
            ('batch_id', '=', classroom.batch_id.id),
            ('program_term_id', '=', classroom.program_term_id.id),
            ('state', 'in', ('published', 'closed')),
        ], order='name desc')

        # Get subject lines for this classroom's subject
        subject_lines = request.env['edu.result.subject.line'].sudo()
        if result_sessions:
            subject_lines = request.env['edu.result.subject.line'].sudo().search([
                ('result_session_id', 'in', result_sessions.ids),
                ('subject_id', '=', classroom.subject_id.id),
                ('section_id', '=', classroom.section_id.id),
            ], order='student_id')

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='results',
            active_sidebar_key='courses',
            page_title='%s - Results' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'Results'],
            result_sessions=result_sessions,
            subject_lines=subject_lines,
        )
        return request.render('edu_portal.teacher_classroom_results', ctx)

    # ══════════════════════════════════════════════════════════════════════
    # Tab 6: People
    # ══════════════════════════════════════════════════════════════════════

    @http.route('/portal/teacher/classroom/<int:classroom_id>/people',
                type='http', auth='user', website=False)
    def teacher_classroom_people(self, classroom_id, **kw):
        classroom, employee, err = self._guard(classroom_id)
        if err:
            return err

        students = get_section_students(classroom.section_id)

        # Build people_rows dicts for the template
        people_rows = []
        for idx, s in enumerate(students):
            name = s.partner_id.name if s.partner_id else (s.display_name or '')
            words = [w for w in name.split() if w]
            initials = (''.join(w[0] for w in words[:2])).upper() or '?'
            people_rows.append({
                'id': s.id,
                'name': name,
                'initials': initials,
                'hue': (idx * 47) % 360,
                'student_id': s.student_no or '',
                'attendance_rate': 100,
                'avg': '',
                'at_risk': False,
                'low_attendance': False,
                'behavior_flag': False,
            })

        ctx = build_portal_context(
            'teacher',
            classroom=classroom,
            active_tab_key='people',
            active_sidebar_key='courses',
            page_title='%s - People' % classroom.name,
            crumbs=['Kopila', 'Courses', classroom.name, 'People'],
            people_rows=people_rows,
            teacher_employee=employee,
        )
        return request.render('edu_portal.teacher_classroom_people', ctx)
