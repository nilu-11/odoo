import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduStudent(models.Model):
    _inherit = 'edu.student'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='When enabled, this student has access to the student portal at /portal.',
    )
    portal_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Portal User',
        compute='_compute_portal_user_id',
        help='Computed from partner_id.user_ids filtered to portal users.',
    )

    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_portal_user_id(self):
        Group = self.env.ref('edu_portal.group_edu_portal_student', raise_if_not_found=False)
        for rec in self:
            if not rec.partner_id or not Group:
                rec.portal_user_id = False
                continue
            users = rec.partner_id.user_ids.filtered(lambda u: Group in u.groups_id)
            rec.portal_user_id = users[:1]

    def action_grant_portal_access(self):
        """Create (or update) a res.users portal user for this student."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Cannot grant portal access: student has no partner record.'))

        group = self.env.ref('edu_portal.group_edu_portal_student')
        existing_user = self.partner_id.user_ids[:1]
        temp_password = _generate_portal_password()

        if existing_user:
            existing_user.write({'groups_id': [(4, group.id)]})
            user = existing_user
        else:
            user = self.env['res.users'].sudo().create({
                'name': self.display_name,
                'login': self.partner_id.email or f'student_{self.id}@portal.local',
                'partner_id': self.partner_id.id,
                'password': temp_password,
                'groups_id': [(6, 0, [group.id])],
            })

        self.portal_access = True
        self._send_portal_welcome_email(user, temp_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Portal user created for %s. Login: %s') % (self.display_name, user.login),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_revoke_portal_access(self):
        """Remove student portal group from the linked user."""
        self.ensure_one()
        group = self.env.ref('edu_portal.group_edu_portal_student')
        if self.portal_user_id:
            self.portal_user_id.sudo().write({'groups_id': [(3, group.id)]})
        self.portal_access = False
        return True

    def _send_portal_welcome_email(self, user, temp_password):
        template = self.env.ref('edu_portal.mail_template_portal_welcome', raise_if_not_found=False)
        if template:
            template.sudo().with_context(
                portal_user=user,
                portal_temp_password=temp_password,
                portal_role='student',
            ).send_mail(self.id, force_send=False)


def _generate_portal_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
