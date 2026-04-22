import logging
import secrets
import string

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='Whether this employee has teacher portal login credentials.',
    )

    # ── Grant portal access ────────────────────────────────────────────────────

    def action_grant_portal_access(self):
        """Create or upgrade a res.users record with the teacher portal group.

        If the employee already has a linked user, add the teacher portal
        group.  Otherwise, create a new portal user with a temporary password
        and send the welcome email.
        """
        self.ensure_one()

        if not self.work_email:
            raise UserError(_(
                'Employee "%s" has no work email. '
                'Set an email before granting portal access.'
            ) % self.name)

        teacher_group = self.env.ref('edu_portal.group_edu_portal_teacher')
        portal_group = self.env.ref('base.group_portal')

        # Use existing linked user if available
        user = self.user_id

        if not user:
            # Search by partner or by email
            user = self.env['res.users'].sudo().search([
                '|',
                ('partner_id', '=', self.address_home_id.id if self.address_home_id else -1),
                ('login', '=', self.work_email),
            ], limit=1)

        temp_password = self._generate_temp_password()

        if user:
            # Add teacher portal group if not already present
            groups_to_add = [(4, teacher_group.id)]
            if not user.sudo().has_group('base.group_portal'):
                groups_to_add.append((4, portal_group.id))
            user.sudo().write({'group_ids': groups_to_add})
            # Link user to employee if not yet linked
            if not self.user_id:
                self.sudo().write({'user_id': user.id})
        else:
            # Create new portal user
            partner = self.address_home_id or self.env['res.partner'].sudo().create({
                'name': self.name,
                'email': self.work_email,
                'company_type': 'person',
            })
            user = self.env['res.users'].sudo().create({
                'name': self.name,
                'login': self.work_email,
                'email': self.work_email,
                'partner_id': partner.id,
                'password': temp_password,
                'group_ids': [
                    (6, 0, [portal_group.id, teacher_group.id]),
                ],
            })
            self.sudo().write({'user_id': user.id})
            if not self.address_home_id:
                self.sudo().write({'address_home_id': partner.id})

        self.write({'portal_access': True})

        # Send welcome email
        self._send_welcome_email(user, temp_password, 'teacher')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Teacher portal access granted for %s.') % self.name,
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Revoke portal access ──────────────────────────────────────────────────

    def action_revoke_portal_access(self):
        """Remove the teacher portal group from the user."""
        self.ensure_one()

        teacher_group = self.env.ref('edu_portal.group_edu_portal_teacher')
        user = self.user_id

        if user and user.sudo().has_group('edu_portal.group_edu_portal_teacher'):
            user.sudo().write({
                'group_ids': [(3, teacher_group.id)],
            })

        self.write({'portal_access': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Revoked'),
                'message': _('Teacher portal access revoked for %s.') % self.name,
                'type': 'warning',
                'sticky': False,
            },
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_temp_password(length=12):
        """Generate a secure temporary password."""
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _send_welcome_email(self, user, password, role):
        """Send the portal welcome email using the portal_mail helper."""
        from .portal_mail import PortalMail

        try:
            body_html = PortalMail.build_welcome_email(user, password, role)
            mail_values = {
                'subject': _('Welcome to the Education Portal'),
                'body_html': body_html,
                'email_to': user.email,
                'email_from': self.env.company.email or self.env.user.email,
                'auto_delete': True,
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
        except Exception as e:
            _logger.warning(
                'Failed to send welcome email to %s: %s', user.login, e,
            )
