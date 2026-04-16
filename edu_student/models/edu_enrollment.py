from odoo import api, fields, models
from odoo.exceptions import UserError


class EduEnrollment(models.Model):
    """
    Extend edu.enrollment to integrate with edu.student.

    Adds:
      - ``student_id`` Many2one to ``edu.student``
      - ``student_created`` computed boolean
      - ``_prepare_student_vals()`` / ``action_create_student()``
      - Auto-create student + portal user on confirm
    """

    _inherit = 'edu.enrollment'

    # ── Student link (defined here, not in base edu_enrollment) ──
    student_id = fields.Many2one(
        'edu.student', string='Student Record',
        ondelete='set null', tracking=True, index=True,
        help='The official student master record created from this enrollment.',
    )
    student_created = fields.Boolean(
        string='Student Created',
        compute='_compute_student_created',
    )

    @api.depends('student_id')
    def _compute_student_created(self):
        for rec in self:
            rec.student_created = bool(rec.student_id)

    # ── Student count helper ──
    student_count = fields.Integer(
        compute='_compute_student_count', string='Students',
    )

    def _compute_student_count(self):
        for rec in self:
            rec.student_count = 1 if rec.student_id else 0

    # ── Override student creation ──
    def _prepare_student_vals(self):
        """Delegate to edu.student's preparation method."""
        self.ensure_one()
        return self.env['edu.student']._prepare_student_vals_from_enrollment(self)

    def action_create_student(self):
        """
        Create an edu.student record from this active enrollment.
        If a student already exists, navigate to it instead of creating a duplicate.
        """
        self.ensure_one()

        if self.state not in ('active',):
            raise UserError(
                'Student record can only be created from an active enrollment.'
            )

        # If student already exists, open it
        if self.student_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.student',
                'res_id': self.student_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Also check by enrollment link (safety net)
        existing = self.env['edu.student'].search(
            [('current_enrollment_id', '=', self.id)], limit=1,
        )
        if existing:
            self.student_id = existing.id
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.student',
                'res_id': existing.id,
                'view_mode': 'form',
                'target': 'current',
            }

        student = self.env['edu.student'].action_create_from_enrollment(self)
        self.student_id = student.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student',
            'res_id': student.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_activate(self):
        """Override to auto-create student and portal user on activation."""
        result = super().action_activate()
        for enrollment in self:
            if not enrollment.student_id:
                try:
                    student = self.env['edu.student'].action_create_from_enrollment(enrollment)
                    enrollment.student_id = student.id
                except UserError as e:
                    # Don't block activation — surface the reason as a log note.
                    enrollment.message_post(
                        body=f'Automatic student creation skipped: {e}',
                    )
                    continue
            enrollment._ensure_portal_user()
        return result

    def _ensure_portal_user(self):
        """Create a portal user for the student's contact if one doesn't exist.

        Uses the partner's email as login. Sends a standard portal invite
        so the student can set their password on first login.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return False
        if partner.user_ids:
            return partner.user_ids[0]
        if not partner.email:
            self.message_post(
                body='Portal user not created: contact has no email address.',
            )
            return False
        Users = self.env['res.users'].sudo()
        # Avoid duplicate login collision
        existing = Users.search([('login', '=', partner.email)], limit=1)
        if existing:
            # Link existing user to this partner if they match
            if existing.partner_id == partner:
                return existing
            self.message_post(
                body=(
                    f'Portal user not created: login "{partner.email}" '
                    'already belongs to another contact.'
                ),
            )
            return False
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if not portal_group:
            return False
        user = Users.with_context(no_reset_password=True).create({
            'partner_id': partner.id,
            'login': partner.email,
        })
        # Replace all default groups with portal only (Odoo 19 renamed
        # groups_id → group_ids).  Using (6,0,...) avoids the
        # "exclusive groups" conflict between Role/User and Role/Portal.
        user.sudo().write({
            'group_ids': [(6, 0, [portal_group.id])],
        })
        # Send portal invite email (set password via reset link)
        try:
            user.action_reset_password()
        except Exception:
            # Email delivery may fail on fresh setups — not fatal.
            pass
        self.message_post(
            body=f'Portal user created for {partner.name} ({partner.email}).',
        )
        return user

    def action_view_student(self):
        """Navigate to the linked student record."""
        self.ensure_one()
        if not self.student_id:
            raise UserError(
                f'Enrollment "{self.enrollment_no}" has no linked student record.'
            )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'edu.student',
            'res_id': self.student_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
