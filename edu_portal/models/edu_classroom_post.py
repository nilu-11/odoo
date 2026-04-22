from odoo import api, fields, models, _


class EduClassroomPost(models.Model):
    """Stream post within a classroom — announcements, material links, etc.

    Visible to the classroom's teacher, students in the section, and
    parents of those students.  Teachers can create/edit/pin/archive
    posts in their own classrooms.
    """

    _name = 'edu.classroom.post'
    _description = 'Classroom Post'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'pinned desc, posted_at desc, id desc'
    _rec_name = 'display_name'

    # ── Core fields ────────────────────────────────────────────────────────────

    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    author_id = fields.Many2one(
        comodel_name='res.users',
        string='Author',
        default=lambda self: self.env.user,
        ondelete='set null',
        index=True,
        tracking=True,
    )
    body = fields.Html(
        string='Body',
        sanitize=True,
        help='Post content. Supports rich text formatting.',
    )
    pinned = fields.Boolean(
        string='Pinned',
        default=False,
        tracking=True,
        help='Pinned posts appear at the top of the stream.',
    )
    posted_at = fields.Datetime(
        string='Posted At',
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )

    # ── Related fields for filtering / record rules ────────────────────────────

    section_id = fields.Many2one(
        comodel_name='edu.section',
        related='classroom_id.section_id',
        store=True,
        index=True,
        string='Section',
    )
    teacher_id = fields.Many2one(
        comodel_name='res.users',
        related='classroom_id.teacher_id',
        store=True,
        index=True,
        string='Teacher',
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        related='classroom_id.batch_id',
        store=True,
        index=True,
        string='Batch',
    )

    # ── Computed display name ──────────────────────────────────────────────────

    @api.depends('classroom_id.name', 'author_id.name', 'posted_at')
    def _compute_display_name(self):
        for rec in self:
            classroom = rec.classroom_id.name or ''
            author = rec.author_id.name or ''
            date_str = rec.posted_at.strftime('%Y-%m-%d %H:%M') if rec.posted_at else ''
            rec.display_name = '%s — %s (%s)' % (classroom, author, date_str) if classroom else 'New Post'

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_pin(self):
        """Toggle the pinned state of the post."""
        for rec in self:
            rec.write({'pinned': not rec.pinned})

    def action_archive_post(self):
        """Archive (soft-delete) the post."""
        self.write({'active': False})
