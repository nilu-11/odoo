from odoo import api, fields, models


class AccountMove(models.Model):
    """
    Lightweight extension of ``account.move`` for EMIS navigation.

    Adds reverse links so that student fee dues can be browsed from an
    invoice or credit note, and a smart button count.
    """

    _inherit = 'account.move'

    # ── Reverse link from dues ────────────────────────────────────────────
    edu_fee_due_ids = fields.One2many(
        'edu.student.fee.due',
        'invoice_id',
        string='Fee Dues',
    )
    edu_fee_due_count = fields.Integer(
        string='Fee Dues',
        compute='_compute_edu_fee_due_count',
    )

    @api.depends('edu_fee_due_ids')
    def _compute_edu_fee_due_count(self):
        for rec in self:
            rec.edu_fee_due_count = len(rec.edu_fee_due_ids)

    # ── Smart button ──────────────────────────────────────────────────────
    def action_view_edu_fee_dues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Dues — {self.name}',
            'res_model': 'edu.student.fee.due',
            'view_mode': 'list,form',
            'domain': [('invoice_id', '=', self.id)],
        }
