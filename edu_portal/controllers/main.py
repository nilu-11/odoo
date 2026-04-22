import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.portal.controllers.portal import CustomerPortal

from .helpers import get_portal_role, is_multi_role, get_parent_children

_logger = logging.getLogger(__name__)


class EduPortalHome(Home):
    """Override login redirect so edu-portal users land on /portal."""

    def _login_redirect(self, uid, redirect=None):
        if redirect:
            return redirect
        user = request.env['res.users'].sudo().browse(uid)
        if user and not user.has_group('base.group_user'):
            role = get_portal_role(user)
            if role != 'none':
                return '/portal'
        return super()._login_redirect(uid, redirect=redirect)


class EduPortalCustomerPortal(CustomerPortal):
    """Override Odoo's /my so edu-portal users go to /portal."""

    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        role = get_portal_role(request.env.user)
        if role != 'none':
            return request.redirect('/portal')
        return super().home(**kw)


class EduPortalMain(http.Controller):
    """Portal dispatcher, role switch, child switch."""

    @http.route('/portal', type='http', auth='user', website=False)
    def portal_dispatch(self, **kw):
        user = request.env.user
        role = get_portal_role(user)

        if role == 'teacher':
            return request.redirect('/portal/teacher/home')
        if role == 'student':
            return request.redirect('/portal/student/home')
        if role == 'parent':
            return request.redirect('/portal/parent/home')
        # No edu role — fall back to Odoo's default portal
        return request.redirect('/my/home')

    @http.route('/portal/role-switch/<string:role>', type='http', auth='user',
                website=False)
    def portal_role_switch(self, role, **kw):
        allowed = ('teacher', 'student', 'parent')
        if role not in allowed:
            return request.redirect('/portal')

        user = request.env.user
        if not is_multi_role(user):
            return request.redirect('/portal')

        group_map = {
            'teacher': 'edu_portal.group_edu_portal_teacher',
            'student': 'edu_portal.group_edu_portal_student',
            'parent': 'edu_portal.group_edu_portal_parent',
        }
        if not user.has_group(group_map[role]):
            return request.redirect('/portal')

        request.session['active_portal_role'] = role
        return request.redirect('/portal')

    @http.route('/portal/parent/switch-child/<int:student_id>', type='http',
                auth='user', website=False)
    def portal_switch_child(self, student_id, **kw):
        user = request.env.user
        role = get_portal_role(user)
        if role != 'parent':
            return request.redirect('/portal')

        children = get_parent_children(user)
        if not children.filtered(lambda c: c.id == student_id):
            return request.redirect('/portal/parent/home')

        request.session['active_child_id'] = student_id
        redirect_url = kw.get('redirect', '/portal/parent/home')
        return request.redirect(redirect_url)
