from odoo import api, fields, models


class EduStudent(models.Model):
    """
    Stage 2 — Extend student with:
      * partner safety (``_ensure_partner_is_customer``)
      * deposit ledger navigation
    """

    _inherit = 'edu.student'

    # ═════════════════════════════════════════════════════════════════════════
    # Deposit Ledger Link
    # ═════════════════════════════════════════════════════════════════════════
    deposit_ledger_ids = fields.One2many(
        'edu.deposit.ledger',
        'student_id',
        string='Deposit Ledger',
    )
    deposit_ledger_count = fields.Integer(
        string='Deposit Ledgers',
        compute='_compute_deposit_ledger_count',
    )
    deposit_balance = fields.Monetary(
        string='Deposit Balance',
        currency_field='finance_currency_id',
        compute='_compute_deposit_balance',
        help='Current security deposit balance across all ledgers.',
    )

    # ── Computed ──────────────────────────────────────────────────────────
    def _compute_deposit_ledger_count(self):
        for rec in self:
            rec.deposit_ledger_count = len(rec.deposit_ledger_ids)

    @api.depends(
        'deposit_ledger_ids.balance',
    )
    def _compute_deposit_balance(self):
        for rec in self:
            rec.deposit_balance = sum(
                rec.deposit_ledger_ids.mapped('balance')
            )

    # ═════════════════════════════════════════════════════════════════════════
    # Partner Safety
    # ═════════════════════════════════════════════════════════════════════════
    def _ensure_partner_is_customer(self):
        """
        Ensure every student's partner has ``customer_rank >= 1`` so
        it appears in Accounting's customer list for invoicing.

        Idempotent — safe to call multiple times.
        """
        partners = self.mapped('partner_id').filtered(
            lambda p: p.customer_rank == 0
        )
        if partners:
            partners.sudo().write({'customer_rank': 1})

    def _ensure_partner(self):
        """
        Safety net for backward compatibility.  If somehow a student
        record exists without a partner (should not happen given
        required=True), auto-create one from the applicant profile.
        """
        for student in self:
            if student.partner_id:
                continue
            profile = student.applicant_profile_id
            name = (
                profile.full_name if profile and hasattr(profile, 'full_name')
                else student.student_no
            )
            vals = {
                'name': name,
                'company_id': student.company_id.id,
                'customer_rank': 1,
            }
            if profile:
                if hasattr(profile, 'email') and profile.email:
                    vals['email'] = profile.email
                if hasattr(profile, 'phone') and profile.phone:
                    vals['phone'] = profile.phone
            partner = self.env['res.partner'].sudo().create(vals)
            student.sudo().write({'partner_id': partner.id})

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Buttons
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_deposit_ledger(self):
        self.ensure_one()
        ledgers = self.deposit_ledger_ids
        if len(ledgers) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'edu.deposit.ledger',
                'res_id': ledgers.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': f'Deposit Ledger — {self.display_name}',
            'res_model': 'edu.deposit.ledger',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
