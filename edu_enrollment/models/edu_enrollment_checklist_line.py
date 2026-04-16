from odoo import api, fields, models
from odoo.exceptions import UserError


class EduEnrollmentChecklistLine(models.Model):
    """
    Lightweight checklist item for enrollment readiness.

    Tracks whether final enrollment requirements (documents, verifications)
    are complete. Required items gate the draft → active flow.
    """

    _name = 'edu.enrollment.checklist.line'
    _description = 'Enrollment Checklist Item'
    _order = 'sequence, id'
    _rec_name = 'name'

    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(
        string='Requirement',
        required=True,
        help='Description of the enrollment requirement.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_required = fields.Boolean(
        string='Required',
        default=True,
        help='If checked, this item must be completed before '
             'enrollment can be activated.',
    )
    is_complete = fields.Boolean(
        string='Complete',
        default=False,
        tracking=True,
    )
    completed_date = fields.Date(
        string='Completed Date',
    )
    completed_by_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Completed By',
    )
    note = fields.Text(
        string='Notes',
    )

    # Convenience
    company_id = fields.Many2one(
        related='enrollment_id.company_id',
        store=True,
        index=True,
    )

    def action_mark_complete(self):
        for rec in self:
            if rec.enrollment_id.state in ('cancelled', 'completed'):
                raise UserError(
                    'Cannot modify checklist on a cancelled or '
                    'completed enrollment.'
                )
            rec.write({
                'is_complete': True,
                'completed_date': fields.Date.context_today(rec),
                'completed_by_user_id': self.env.uid,
            })

    def action_mark_incomplete(self):
        for rec in self:
            if rec.enrollment_id.state in ('active', 'cancelled', 'completed'):
                raise UserError(
                    'Cannot modify checklist on an active, cancelled, or '
                    'completed enrollment.'
                )
            rec.write({
                'is_complete': False,
                'completed_date': False,
                'completed_by_user_id': False,
            })
