"""Root portal controllers — redirection and role switching."""
from odoo import http
from odoo.http import request
from .helpers import get_portal_role, set_portal_role, set_active_child


class PortalMainController(http.Controller):

    @http.route('/portal', type='http', auth='user', website=False)
    def portal_home(self, **kw):
        """Redirect to role-specific home."""
        user = request.env.user
        role = get_portal_role(user)
        if role == 'teacher':
            return request.redirect('/portal/teacher/home')
        elif role == 'student':
            return request.redirect('/portal/student/home')
        elif role == 'parent':
            return request.redirect('/portal/parent/home')
        else:
            # No portal role — send to standard Odoo backend
            return request.redirect('/odoo')

    @http.route('/portal/role-switch/<string:role>', type='http', auth='user', methods=['GET', 'POST'])
    def role_switch(self, role, **kw):
        """Switch active role for multi-role users."""
        if role not in ('student', 'parent', 'teacher'):
            return request.not_found()
        user = request.env.user
        if user.portal_role != 'multi':
            return request.not_found()
        set_portal_role(role)
        return request.redirect('/portal')

    @http.route('/portal/parent/switch-child/<int:student_id>', type='http', auth='user')
    def switch_child(self, student_id, **kw):
        """Set active child for parent portal users."""
        from .helpers import get_parent_children
        user = request.env.user
        children = get_parent_children(user)
        if student_id not in children.ids:
            return request.not_found()
        set_active_child(student_id)
        return request.redirect('/portal/parent/home')
