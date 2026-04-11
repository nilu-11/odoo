"""Classroom Stream announcements.

Teachers post rich-text announcements to a classroom's Stream. Students
see them read-only. Attachments come for free via mail.thread — the
composer uses message_main_attachment_id plus standard message_attach.

Scope is deliberately minimal: no comments, reactions, mentions, or
scheduled posts. Pinning and soft-archive (active=False) are the only
post-level controls.
"""
from odoo import api, fields, models


class EduClassroomPost(models.Model):
    _name = 'edu.classroom.post'
    _description = 'Classroom Stream Post'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pinned desc, posted_at desc, id desc'

    # ═══ Relational ═══
    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        required=True,
        ondelete='cascade',
        index=True,
    )
    author_id = fields.Many2one(
        comodel_name='res.users',
        string='Author',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        index=True,
    )
    author_employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Author (Employee)',
        related='author_id.employee_id',
        store=True,
        help="Resolved from author_id for avatar/name display in feed.",
    )

    # ═══ Content ═══
    body = fields.Html(
        string='Body',
        required=True,
        sanitize=True,
        sanitize_attributes=True,
    )

    # ═══ State ═══
    pinned = fields.Boolean(
        string='Pinned',
        default=False,
        tracking=True,
        help="Pinned posts appear at the top of the stream feed.",
    )
    posted_at = fields.Datetime(
        string='Posted At',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    # ═══ Helpers ═══

    @api.model_create_multi
    def create(self, vals_list):
        """Stamp posted_at explicitly even if caller didn't pass it."""
        for vals in vals_list:
            vals.setdefault('posted_at', fields.Datetime.now())
        return super().create(vals_list)

    def action_toggle_pin(self):
        """Flip the pinned flag. Used by the portal HTMX button."""
        for rec in self:
            rec.pinned = not rec.pinned
        return True

    def action_archive_post(self):
        """Soft-delete by clearing active. Used by the portal archive button."""
        self.write({'active': False})
        return True
