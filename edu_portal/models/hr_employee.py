import secrets
import string
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    portal_access = fields.Boolean(
        string='Portal Access',
        default=False,
        tracking=True,
        help='When enabled, this teaching staff has access to the teacher portal at /portal.',
    )
    portal_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Portal User',
        compute='_compute_portal_user_id',
    )

    @api.depends('user_id')
    def _compute_portal_user_id(self):
        Group = self.env.ref('edu_portal.group_edu_portal_teacher', raise_if_not_found=False)
        for rec in self:
            if rec.user_id and Group and Group in rec.user_id.groups_id:
                rec.portal_user_id = rec.user_id
            else:
                rec.portal_user_id = False

    def action_grant_portal_access(self):
        """Create or upgrade a res.users record for this employee as a teacher portal user."""
        self.ensure_one()
        if not self.is_teaching_staff:
            raise UserError(_('Portal access is only available for teaching staff.'))

        group = self.env.ref('edu_portal.group_edu_portal_teacher')
        temp_password = _generate_portal_password()

        if self.user_id:
            # Existing user — add the teacher portal group
            self.user_id.write({'groups_id': [(4, group.id)]})
            user = self.user_id
        elif self.work_contact_id and self.work_contact_id.user_ids:
            user = self.work_contact_id.user_ids[:1]
            user.write({'groups_id': [(4, group.id)]})
            self.user_id = user
        else:
            # Create new user linked to employee
            login = self.work_email or f'teacher_{self.id}@portal.local'
            user = self.env['res.users'].sudo().create({
                'name': self.name,
                'login': login,
                'password': temp_password,
                'groups_id': [(6, 0, [group.id])],
            })
            self.user_id = user

        self.portal_access = True
        self._send_portal_welcome_email(user, temp_password)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Portal Access Granted'),
                'message': _('Teacher portal user created for %s. Login: %s') % (self.name, user.login),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_revoke_portal_access(self):
        self.ensure_one()
        group = self.env.ref('edu_portal.group_edu_portal_teacher')
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
                portal_role='teacher',
            ).send_mail(self.id, force_send=False)


def _generate_portal_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
