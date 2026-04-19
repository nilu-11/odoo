"""Shared helpers for edu_portal controllers.

This module centralises:

* role resolution (respecting multi-role session overrides),
* entity lookups (teacher employee, student, guardian, parent children),
* classroom-access guarding,
* the portal context builder that every page template consumes.

The **single resolution point** for the portal extension registry lives
in ``_resolve_portal_registry``. Controllers never query the registry
models directly — they call ``build_portal_context``, which internally
reads the registry, resolves visibility/badge methods, and hands back
a fully-populated context dict.

Authorship note — the ``edu_hr`` module overrides
``edu.classroom.teacher_id`` (and exam paper / attendance /
assessment ``teacher_id``) from ``res.users`` to ``hr.employee``. All
auth comparisons here therefore resolve the current user to their
linked ``hr.employee`` via ``get_teacher_employee`` and compare that
record to ``teacher_id``. If a teacher user has no linked employee,
they are treated as having no classrooms.
"""
from odoo.http import request


# ─── Role resolution ───────────────────────────────────────────────

def get_portal_role(user):
    """Return the effective portal role for this user.

    Multi-role users fall back to a session-stored active role, then to
    ``teacher`` if no session value is set.
    """
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


# ─── Entity lookups ────────────────────────────────────────────────

def get_teacher_employee(user):
    """Return the hr.employee linked to this user (used for auth).

    With ``edu_hr`` installed, ``edu.classroom.teacher_id`` and friends
    are m2o to ``hr.employee``, so this record is what every ownership
    check must compare against. Returns ``None`` if no employee is
    linked — the caller is then responsible for treating the user as
    unauthorised.
    """
    emp = request.env['hr.employee'].sudo().search(
        [('user_id', '=', user.id)], limit=1,
    )
    return emp or None


def get_student_record(user):
    """Return the edu.student linked to this user's partner, or None."""
    if not user.partner_id:
        return None
    return request.env['edu.student'].sudo().search(
        [('partner_id', '=', user.partner_id.id)], limit=1,
    ) or None


def get_guardian_record(user):
    """Return the edu.guardian linked to this user's partner, or None."""
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
    """Return the selected child for a parent, or first child as fallback."""
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


# ─── Classroom access guard ────────────────────────────────────────

def guard_classroom_access(classroom_id, role):
    """Load a classroom and verify the current user is authorised for it.

    Returns the ``edu.classroom`` record on success, or ``None`` if the
    classroom does not exist or the user is not authorised.

    * ``teacher`` → the user's linked ``hr.employee`` must equal
      ``classroom.teacher_id``. With ``edu_hr`` installed, that field
      is m2o to ``hr.employee``, so auth resolves through the employee
      — not the user record.
    * ``student`` → the current user's student record must have an
      ``active`` progression history whose ``section_id`` matches the
      classroom's ``section_id``.
    """
    classroom = request.env['edu.classroom'].sudo().browse(classroom_id)
    if not classroom.exists():
        return None

    user = request.env.user

    if role == 'teacher':
        employee = get_teacher_employee(user)
        if not employee:
            return None
        return classroom if classroom.teacher_id == employee else None

    if role == 'student':
        student = get_student_record(user)
        if not student:
            return None
        history = request.env['edu.student.progression.history'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'active'),
            ('section_id', '=', classroom.section_id.id),
        ], limit=1)
        return classroom if history else None

    return None


# ─── Portal extension registry — single resolution point ──────────

def _call_dotted(dotted):
    """Call an ``model.method_name`` dotted path and return the result.

    Returns ``(ok, value)``. ``ok=False`` means the model or method was
    missing — caller should treat the record as visible-no-badge and
    never raise. Any other exception propagates (it's a real bug in the
    target method and should surface to logs).
    """
    if not dotted:
        return True, None
    model_name, method_name = dotted.rsplit('.', 1)
    try:
        model = request.env[model_name]
    except KeyError:
        return False, None
    method = getattr(model, method_name, None)
    if method is None:
        return False, None
    return True, method()


def _resolve_portal_registry(role, classroom=None):
    """Read registry models once per request and return resolved lists.

    Returns a dict::

        {
            'sidebar_items': [
                {'key', 'label', 'icon', 'url', 'sequence', 'badge'},
                ...
            ],
            'classroom_tabs': [
                {'key', 'label', 'icon', 'url', 'sequence'},
                ...
            ] or [],
        }

    Visibility methods returning falsy remove the record from the
    rendered list. Missing models/methods are silently skipped and the
    record is treated as visible-no-badge (never crashes the portal).
    """
    role_domain = ['|', ('role', '=', role), ('role', '=', 'all')]
    SidebarItem = request.env['edu.portal.sidebar.item']
    items_qs = SidebarItem.search([('active', '=', True), *role_domain])

    sidebar_items = []
    for item in items_qs:
        vis_ok, visible = _call_dotted(item.visibility_method)
        if vis_ok and visible is False:
            continue
        badge_ok, badge = _call_dotted(item.badge_method)
        sidebar_items.append({
            'key': item.key,
            'label': item.label,
            'icon': item.icon or '',
            'url': item.url,
            'sequence': item.sequence,
            'group': item.group or '',
            'badge': badge if badge_ok else None,
        })

    classroom_tabs = []
    if classroom is not None:
        TabRegistry = request.env['edu.portal.classroom.tab']
        tabs_qs = TabRegistry.search([('active', '=', True), *role_domain])
        for tab in tabs_qs:
            vis_ok, visible = _call_dotted(tab.visibility_method)
            if vis_ok and visible is False:
                continue
            classroom_tabs.append({
                'key': tab.key,
                'label': tab.label,
                'icon': tab.icon or '',
                'url': tab.route_pattern.format(classroom_id=classroom.id),
                'sequence': tab.sequence,
            })

    return {
        'sidebar_items': sidebar_items,
        'classroom_tabs': classroom_tabs,
    }


def build_portal_context(
    active_sidebar_key=None,
    active_tab_key=None,
    classroom=None,
    page_title=None,
):
    """Build the dict every portal template consumes.

    Centralises registry resolution, sidebar collapsed state, role
    detection, and standard page variables. Controllers call this once
    per handler and then merge in their own page-specific keys.
    """
    user = request.env.user
    role = get_portal_role(user)
    resolved = _resolve_portal_registry(role, classroom=classroom)
    return {
        'user': user,
        'portal_role': role,
        'page_title': page_title or '',
        'sidebar_collapsed': is_sidebar_collapsed(),
        'active_sidebar_key': active_sidebar_key,
        'active_tab_key': active_tab_key,
        'classroom': classroom,
        'sidebar_items': resolved['sidebar_items'],
        'classroom_tabs': resolved['classroom_tabs'],
        # Legacy alias — old templates still read `active_item`.
        'active_item': active_sidebar_key,
    }


# ─── Legacy compatibility shim ─────────────────────────────────────

def base_context(active_item=None, page_title=None):
    """Backwards-compatible wrapper used by not-yet-migrated controllers.

    Delegates to ``build_portal_context``. Will be removed after all
    controllers have been migrated to call ``build_portal_context``
    directly (see Phase 11 of the refactor).
    """
    return build_portal_context(
        active_sidebar_key=active_item,
        page_title=page_title,
    )


def teacher_owns_classroom(user_or_employee, classroom):
    """Legacy compat — returns True if the current user owns the classroom.

    With ``edu_hr`` installed, ``classroom.teacher_id`` is m2o to
    ``hr.employee``. This shim resolves the current request user to
    their linked employee and compares to ``classroom.teacher_id``.
    Removed once all callers have migrated to ``guard_classroom_access``.
    """
    if not classroom:
        return False
    employee = get_teacher_employee(request.env.user)
    if not employee:
        return False
    return classroom.teacher_id == employee
