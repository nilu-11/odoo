import logging
import secrets
import string

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduGuardian(models.Model):
    _inherit = 'edu.guardian'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='Whether this guardian/parent has portal login credentials.',
    )

    # ── Grant portal access ────────────────────────────────────────────────────

    def action_grant_portal_access(self):
        """Create or upgrade a res.users record with the parent portal group.

        If the guardian's partner already has a user, add the parent portal
        group.  Otherwise, create a new portal user with a temporary password
        and send the welcome email.
        """
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_(
                'Guardian "%s" has no contact partner.'
            ) % self.full_name)
        if not self.partner_id.email:
            raise UserError(_(
                'Guardian "%s" has no email address on their contact. '
                'Set an email before granting portal access.'
            ) % self.full_name)

        parent_group = self.env.ref('edu_portal.group_edu_portal_parent')
        portal_group = self.env.ref('base.group_portal')

        # Find existing user for this partner
        user = self.env['res.users'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)

        temp_password = self._generate_temp_password()

        if user:
            # Add parent portal group if not already present
            groups_to_add = [(4, parent_group.id)]
            if not user.sudo().has_group('base.group_portal'):
                groups_to_add.append((4, portal_group.id))
            user.sudo().write({'group_ids': groups_to_add})
        else:
            # Create new portal user
            user = self.env['res.users'].sudo().create({
                'name': self.partner_id.name,
                'login': self.partner_id.email,
                'email': self.partner_id.email,
                'partner_id': self.partner_id.id,
                'password': temp_password,
                'group_ids': [
                    (6, 0, [portal_group.id, parent_group.id]),
                ],
            })

        self.write({'portal_access': True})

        # Send welcome email
        self._send_welcome_email(user, temp_password, 'parent')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Parent portal access granted for %s.') % self.full_name,
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Revoke portal access ──────────────────────────────────────────────────

    def action_revoke_portal_access(self):
        """Remove the parent portal group from the user."""
        self.ensure_one()

        parent_group = self.env.ref('edu_portal.group_edu_portal_parent')
        user = self.env['res.users'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)

        if user and user.sudo().has_group('edu_portal.group_edu_portal_parent'):
            user.sudo().write({
                'group_ids': [(3, parent_group.id)],
            })

        self.write({'portal_access': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Revoked'),
                'message': _('Parent portal access revoked for %s.') % self.full_name,
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
