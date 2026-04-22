import logging

from odoo.http import request

_logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Role detection
# ════════════════════════════════��═══════════════════════════════════���════════

def get_portal_role(user):
    """Return effective portal role: 'teacher'|'student'|'parent'|'multi'|'none'."""
    is_student = user.has_group('edu_portal.group_edu_portal_student')
    is_parent = user.has_group('edu_portal.group_edu_portal_parent')
    is_teacher = user.has_group('edu_portal.group_edu_portal_teacher')
    roles = sum([is_student, is_parent, is_teacher])
    if roles == 0:
        return 'none'
    if roles > 1:
        # Multi-role: check session override
        return request.session.get('active_portal_role', 'teacher')
    if is_teacher:
        return 'teacher'
    if is_student:
        return 'student'
    return 'parent'


def is_multi_role(user):
    """Check if user has multiple portal roles."""
    count = sum([
        user.has_group('edu_portal.group_edu_portal_student'),
        user.has_group('edu_portal.group_edu_portal_parent'),
        user.has_group('edu_portal.group_edu_portal_teacher'),
    ])
    return count > 1


# ═══════════���══════════════════════════���══════════════════════════════════════
# Record lookups
# ════════════════════════════���══════════════════════════════��═════════════════

def get_teacher_employee(user):
    """Return the hr.employee record for the current user (teaching staff)."""
    return request.env['hr.employee'].sudo().search([
        ('user_id', '=', user.id),
        ('is_teaching_staff', '=', True),
    ], limit=1)


def get_student_record(user):
    """Return the edu.student record linked to the current user's partner."""
    partner_id = user.sudo().partner_id.id
    return request.env['edu.student'].sudo().search([
        ('partner_id', '=', partner_id),
    ], limit=1)


def get_guardian_record(user):
    """Return the edu.guardian record linked to the current user's partner."""
    partner_id = user.sudo().partner_id.id
    return request.env['edu.guardian'].sudo().search([
        ('partner_id', '=', partner_id),
    ], limit=1)


def get_parent_children(user):
    """Return edu.student recordset for all children linked to this parent.

    Path: res.users -> res.partner -> edu.guardian -> edu.applicant.guardian.rel
          -> edu.applicant.profile -> edu.student
    """
    guardian = get_guardian_record(user)
    if not guardian:
        return request.env['edu.student'].sudo()

    rels = request.env['edu.applicant.guardian.rel'].sudo().search([
        ('guardian_id', '=', guardian.id),
        ('active', '=', True),
    ])
    applicant_profile_ids = rels.mapped('applicant_profile_id').ids
    if not applicant_profile_ids:
        return request.env['edu.student'].sudo()

    students = request.env['edu.student'].sudo().search([
        ('applicant_profile_id', 'in', applicant_profile_ids),
    ])
    return students


def get_active_child(user):
    """Return the currently active child for a parent user."""
    children = get_parent_children(user)
    if not children:
        return None
    child_id = request.session.get('active_child_id')
    if child_id:
        child = children.filtered(lambda c: c.id == int(child_id))
        if child:
            return child[0]
    return children[0]


# ══════════════════════════════════════════���═════════════════════════════��════
# Classroom access guard
# ════════════���═══════════════════��═══════════════════════════════��════════════

def guard_classroom_access(classroom_id, role):
    """Verify user can access this classroom. Returns classroom or None."""
    classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
    if not classroom.exists():
        return None
    user = request.env.user

    if role == 'teacher':
        employee = get_teacher_employee(user)
        if not employee or classroom.teacher_id != employee:
            return None

    elif role == 'student':
        student = get_student_record(user)
        if not student:
            return None
        # Check student has active progression in this classroom's section
        prog = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('section_id', '=', classroom.section_id.id),
            ('state', '=', 'active'),
        ], limit=1)
        if not prog:
            return None

    return classroom


# ═════════════════════════���═══════════════════════════════════════════════════
# Section students helper
# ═════════════════════════════════���═══════════════════════════════════════════

def get_section_students(section):
    """Return edu.student recordset for all active students in a section."""
    histories = request.env['edu.student.progression.history'].sudo().search([
        ('section_id', '=', section.id),
        ('state', '=', 'active'),
    ])
    return histories.mapped('student_id')


# ══════════���══════════════════��══════════════════════════════��════════════════
# Portal context builder
# ══════════════════════════════════���══════════════════════════════════════════

def build_portal_context(role, **kwargs):
    """Build the common context dict for all portal pages."""
    user = request.env.user

    # ── Sidebar items (hardcoded, not from DB) ─────────────────────────────

    teacher_sidebar = [
        {'group': 'Teach', 'items': [
            {'key': 'today', 'label': 'Today', 'icon': 'home', 'url': '/portal/teacher/home'},
            {'key': 'courses', 'label': 'Courses', 'icon': 'book', 'url': '/portal/teacher/courses'},
            {'key': 'attendance', 'label': 'Attendance', 'icon': 'check', 'url': '/portal/teacher/attendance'},
            {'key': 'marking', 'label': 'Marking', 'icon': 'pen', 'url': '/portal/teacher/marking'},
            {'key': 'gradebook', 'label': 'Gradebook', 'icon': 'grid', 'url': '/portal/teacher/gradebook'},
            {'key': 'reports', 'label': 'Report cards', 'icon': 'paper', 'url': '/portal/teacher/reports'},
        ]},
        {'group': 'Communicate', 'items': [
            {'key': 'messages', 'label': 'Messages', 'icon': 'msg', 'url': '/portal/teacher/messages'},
            {'key': 'announcements', 'label': 'Announcements', 'icon': 'mega', 'url': '/portal/teacher/announcements'},
            {'key': 'calendar', 'label': 'Calendar', 'icon': 'cal', 'url': '/portal/teacher/calendar'},
        ]},
        {'group': 'Records', 'items': [
            {'key': 'behavior', 'label': 'Behavior notes', 'icon': 'flag', 'url': '/portal/teacher/behavior'},
            {'key': 'fees', 'label': 'Fees overview', 'icon': 'coin', 'url': '/portal/teacher/fees'},
        ]},
    ]

    student_sidebar = [
        {'group': 'Learn', 'items': [
            {'key': 'home', 'label': 'Home', 'icon': 'home', 'url': '/portal/student/home'},
            {'key': 'courses', 'label': 'Courses', 'icon': 'book', 'url': '/portal/student/courses'},
        ]},
        {'group': 'Records', 'items': [
            {'key': 'fees', 'label': 'Fees', 'icon': 'coin', 'url': '/portal/student/fees'},
        ]},
        {'group': 'Account', 'items': [
            {'key': 'profile', 'label': 'My Profile', 'icon': 'user', 'url': '/portal/student/profile'},
        ]},
    ]

    parent_sidebar = [
        {'group': 'My Child', 'items': [
            {'key': 'home', 'label': 'Overview', 'icon': 'home', 'url': '/portal/parent/home'},
            {'key': 'attendance', 'label': 'Attendance', 'icon': 'check', 'url': '/portal/parent/attendance'},
            {'key': 'results', 'label': 'Results', 'icon': 'grid', 'url': '/portal/parent/results'},
            {'key': 'assessments', 'label': 'Assessments', 'icon': 'pen', 'url': '/portal/parent/assessments'},
            {'key': 'fees', 'label': 'Fees', 'icon': 'coin', 'url': '/portal/parent/fees'},
        ]},
        {'group': 'Account', 'items': [
            {'key': 'profile', 'label': 'My Profile', 'icon': 'user', 'url': '/portal/parent/profile'},
        ]},
    ]

    sidebar_map = {
        'teacher': teacher_sidebar,
        'student': student_sidebar,
        'parent': parent_sidebar,
    }

    # ── Teacher courses for sidebar ────────────────────────────────────────

    teacher_courses = []
    if role == 'teacher':
        employee = get_teacher_employee(user)
        if employee:
            classrooms = request.env['edu.classroom'].sudo().search([
                ('teacher_id', '=', employee.id),
                ('state', '=', 'active'),
            ], order='name')
            teacher_courses = [
                {
                    'id': cl.id,
                    'code': cl.code or '',
                    'code_num': (cl.subject_id.code or '')[:3].upper() if cl.subject_id else '',
                    'title': cl.name or '',
                    'color': 'saffron',
                    'semester': cl.program_term_id.name if cl.program_term_id else '',
                    'section': cl.section_id.name if cl.section_id else '',
                    'subject': cl.subject_id.name if cl.subject_id else '',
                    'credits': 3,
                    'students': 0,
                    'progress_pct': 0,
                    'current_week': 0,
                    'total_weeks': 15,
                    'next_class': '',
                    'room': '',
                }
                for cl in classrooms
            ]

    # ── Assemble context ───────────────────���───────────────────────────────

    _name = user.sudo().name or ''
    _words = [w for w in _name.split() if w]
    _initials = (''.join(w[0] for w in _words[:2])).upper() or 'U'
    _role_labels = {'teacher': 'Teacher', 'student': 'Student', 'parent': 'Parent', 'multi': 'Multiple roles'}

    ctx = {
        'user': user.sudo(),
        'portal_role': role,
        'active_role': role,
        'is_multi_role': is_multi_role(user),
        'sidebar_groups': sidebar_map.get(role, []),
        'active_sidebar_key': kwargs.get('active_sidebar_key', ''),
        'page_title': kwargs.get('page_title', 'Portal'),
        'crumbs': kwargs.get('crumbs', ['Kopila']),
        'teacher_courses': teacher_courses,
        'user_initials': _initials,
        'user_display_name': _name,
        'user_role_label': _role_labels.get(role, 'Portal user'),
    }

    # ── Parent-specific context ─────────────────────��──────────────────────

    if role == 'parent':
        ctx['children'] = get_parent_children(user)
        _active_child_orm = get_active_child(user)
        if _active_child_orm:
            _cn = _active_child_orm.partner_id.name if _active_child_orm.partner_id else (_active_child_orm.display_name or '')
            _cw = [w for w in _cn.split() if w]
            ctx['active_child'] = {
                'id': _active_child_orm.id,
                'name': _cn,
                'first_name': _cw[0] if _cw else _cn,
                'initials': (''.join(w[0] for w in _cw[:2])).upper() or '?',
                'student_id': _active_child_orm.student_no or '',
                'program': '',
            }
            ctx['active_child_id'] = _active_child_orm.id
        else:
            ctx['active_child'] = None
            ctx['active_child_id'] = None

    # ── Classroom-specific context ���────────────────────────────────────────

    if 'classroom' in kwargs:
        cl = kwargs['classroom']
        _teacher = cl.teacher_id
        classroom_dict = {
            'id': cl.id,
            'code': cl.code or '',
            'title': cl.name or '',
            'subject': cl.subject_id.name if cl.subject_id else '',
            'semester': cl.program_term_id.name if cl.program_term_id else '',
            'section': cl.section_id.name if cl.section_id else '',
            'credits': 3,
            'students': 0,
            'current_week': 0,
            'total_weeks': 15,
            'next_class': '',
            'room': '',
            'schedule': '',
            'teacher_name': _teacher.name if _teacher else '',
            'teacher_initials': (''.join(w[0] for w in (_teacher.name or '').split()[:2])).upper() if _teacher else '',
            'teacher_title': _teacher.job_title or '' if _teacher else '',
        }
        ctx['classroom'] = classroom_dict
        ctx['active_classroom_id'] = cl.id
        ctx['active_tab_key'] = kwargs.get('active_tab_key', 'stream')

        # Hardcoded classroom tabs
        if role == 'teacher':
            ctx['classroom_tabs'] = [
                {'key': 'stream', 'label': 'Stream', 'icon': 'mega',
                 'url': '/portal/teacher/classroom/%d/stream' % cl.id},
                {'key': 'attendance', 'label': 'Attendance', 'icon': 'check',
                 'url': '/portal/teacher/classroom/%d/attendance' % cl.id},
                {'key': 'exams', 'label': 'Exams', 'icon': 'paper',
                 'url': '/portal/teacher/classroom/%d/exams' % cl.id},
                {'key': 'assessments', 'label': 'Assessments', 'icon': 'pen',
                 'url': '/portal/teacher/classroom/%d/assessments' % cl.id},
                {'key': 'results', 'label': 'Results', 'icon': 'grid',
                 'url': '/portal/teacher/classroom/%d/results' % cl.id},
                {'key': 'people', 'label': 'People', 'icon': 'users',
                 'url': '/portal/teacher/classroom/%d/people' % cl.id},
            ]
        elif role == 'student':
            ctx['classroom_tabs'] = [
                {'key': 'stream', 'label': 'Stream', 'icon': 'mega',
                 'url': '/portal/student/classroom/%d/stream' % cl.id},
                {'key': 'attendance', 'label': 'Attendance', 'icon': 'check',
                 'url': '/portal/student/classroom/%d/attendance' % cl.id},
                {'key': 'exams', 'label': 'Exams', 'icon': 'paper',
                 'url': '/portal/student/classroom/%d/exams' % cl.id},
                {'key': 'assessments', 'label': 'Assessments', 'icon': 'pen',
                 'url': '/portal/student/classroom/%d/assessments' % cl.id},
                {'key': 'results', 'label': 'Results', 'icon': 'grid',
                 'url': '/portal/student/classroom/%d/results' % cl.id},
                {'key': 'people', 'label': 'People', 'icon': 'users',
                 'url': '/portal/student/classroom/%d/people' % cl.id},
            ]
        # Remove ORM record from kwargs so ctx.update doesn't overwrite the dict
        kwargs.pop('classroom')

    ctx.update(kwargs)
    return ctx
