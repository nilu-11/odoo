"""Shared helpers for edu_portal controllers."""
from odoo.http import request


def get_portal_role(user):
    """Return the effective portal role for this user, respecting session override for multi-role users."""
    role = user.portal_role
    if role == 'multi':
        session_role = request.session.get('active_portal_role')
        return session_role or 'teacher'
    return role


def set_portal_role(role):
    """Store the active portal role for multi-role users in the session."""
    request.session['active_portal_role'] = role


def is_sidebar_collapsed():
    """Read sidebar collapsed state from cookie."""
    return request.httprequest.cookies.get('portal_sidebar_collapsed') == '1'


def get_teacher_employee(user):
    """Return the hr.employee linked to this teacher user, or None."""
    emp = request.env['hr.employee'].sudo().search(
        [('user_id', '=', user.id)], limit=1,
    )
    return emp or None


def get_student_record(user):
    """Return the edu.student linked to this student user's partner, or None."""
    if not user.partner_id:
        return None
    return request.env['edu.student'].sudo().search(
        [('partner_id', '=', user.partner_id.id)], limit=1,
    ) or None


def get_guardian_record(user):
    """Return the edu.guardian linked to this parent user's partner, or None."""
    if not user.partner_id:
        return None
    return request.env['edu.guardian'].sudo().search(
        [('partner_id', '=', user.partner_id.id)], limit=1,
    ) or None


def get_parent_children(user):
    """Return the list of edu.student records (children) for a parent user."""
    guardian = get_guardian_record(user)
    if not guardian:
        return request.env['edu.student'].sudo()
    applicant_profiles = guardian.applicant_ids.mapped('applicant_id')
    return request.env['edu.student'].sudo().search(
        [('applicant_profile_id', 'in', applicant_profiles.ids)],
    )


def get_active_child(user):
    """Return the currently selected child for a parent, or the first child if none selected."""
    children = get_parent_children(user)
    if not children:
        return None
    active_id = request.session.get('active_child_id')
    if active_id:
        active = children.filtered(lambda s: s.id == active_id)
        if active:
            return active
    return children[0]


def set_active_child(student_id):
    request.session['active_child_id'] = student_id


def teacher_owns_classroom(employee, classroom):
    """Assert a teacher owns a given classroom. Return True/False."""
    if not employee or not classroom:
        return False
    return classroom.teacher_id == employee


def base_context(active_item=None, page_title=None):
    """Build the base context dict all portal templates need."""
    user = request.env.user
    role = get_portal_role(user)
    return {
        'user': user,
        'portal_role': role,
        'page_title': page_title or '',
        'sidebar_collapsed': is_sidebar_collapsed(),
        'active_item': active_item,
    }
