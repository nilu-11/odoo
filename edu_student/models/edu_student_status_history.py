from odoo import api, fields, models


class EduStudentStatusHistory(models.Model):
    """
    Audit trail for student lifecycle state changes.

    Every transition (e.g. active → on_leave) is logged with
    timestamp, user, and optional reason.  This provides a
    complete history for compliance and reporting.
    """

    _name = 'edu.student.status.history'
    _description = 'Student Status History'
    _order = 'changed_on desc, id desc'
    _rec_name = 'display_name'

    student_id = fields.Many2one(
        'edu.student', string='Student', required=True,
        ondelete='cascade', index=True,
    )
    old_state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('on_leave', 'On Leave'),
            ('suspended', 'Suspended'),
            ('withdrawn', 'Withdrawn'),
            ('graduated', 'Graduated'),
            ('alumni', 'Alumni'),
            ('inactive', 'Inactive'),
        ],
        string='Previous Status', required=True,
    )
    new_state = fields.Selection(
        selection=[
            ('active', 'Active'),
            ('on_leave', 'On Leave'),
            ('suspended', 'Suspended'),
            ('withdrawn', 'Withdrawn'),
            ('graduated', 'Graduated'),
            ('alumni', 'Alumni'),
            ('inactive', 'Inactive'),
        ],
        string='New Status', required=True,
    )
    changed_on = fields.Datetime(
        string='Changed On', default=fields.Datetime.now,
        required=True, readonly=True,
    )
    changed_by = fields.Many2one(
        'res.users', string='Changed By',
        default=lambda self: self.env.uid,
        required=True, readonly=True,
    )
    reason = fields.Text(string='Reason')
    student_no = fields.Char(
        related='student_id.student_no', string='Student No.',
        store=True, readonly=True,
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('student_id.student_no', 'old_state', 'new_state', 'changed_on')
    def _compute_display_name(self):
        for rec in self:
            dt = fields.Datetime.to_string(rec.changed_on) if rec.changed_on else ''
            rec.display_name = (
                f'{rec.student_no or "?"}: '
                f'{rec.old_state or "?"} → {rec.new_state or "?"} '
                f'({dt})'
            )
