"""Root portal controllers — redirection and role switching."""
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.portal.controllers.portal import CustomerPortal
from .helpers import get_portal_role, set_portal_role, set_active_child


def _is_emis_portal_user(user):
    """Return True if the user has an EMIS portal role (student/parent/teacher)."""
    return user.portal_role in ('student', 'parent', 'teacher', 'multi')


class PortalHome(Home):
    """Override login redirect so portal users land on /portal after login."""

    def _login_redirect(self, uid, redirect=None):
        # Honor an explicit redirect parameter (e.g. user was going somewhere specific)
        if redirect:
            return super()._login_redirect(uid, redirect=redirect)
        user = request.env['res.users'].sudo().browse(uid)
        # Only redirect portal users (non-internal) with an EMIS portal role
        if not user._is_internal() and _is_emis_portal_user(user):
            return '/portal'
        return super()._login_redirect(uid, redirect=redirect)


class PortalCustomerPortalOverride(CustomerPortal):
    """Override Odoo's default /my portal home so EMIS portal users are
    redirected to our custom /portal instead of seeing Odoo's default portal."""

    def home(self, **kw):
        user = request.env.user
        if _is_emis_portal_user(user):
            return request.redirect('/portal')
        return super().home(**kw)


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

    @http.route('/web/login_successful', type='http', auth='user', website=False)
    def login_successful_redirect(self, **kw):
        """Override the default login_successful landing for external users."""
        user = request.env.user
        if _is_emis_portal_user(user):
            return request.redirect('/portal')
        return request.redirect('/odoo' if user._is_internal() else '/web/login')

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
