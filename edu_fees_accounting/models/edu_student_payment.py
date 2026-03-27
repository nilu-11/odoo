from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class EduStudentPayment(models.Model):
    """
    Stage 2 — Extend student payment with Odoo Accounting integration.

    On posting, the EMIS payment now creates a corresponding
    ``account.payment`` (inbound customer payment), posts it, and
    reconciles it with the related student fee invoices.

    Backward-compatible: if no payment journal is configured or
    assigned, EMIS posting still works as Stage 1 (internal only).
    """

    _inherit = 'edu.student.payment'

    # ═════════════════════════════════════════════════════════════════════════
    # Accounting Link
    # ═════════════════════════════════════════════════════════════════════════
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Accounting Payment',
        ondelete='set null',
        copy=False,
        index=True,
        tracking=True,
        help='Accounting entry created when this payment is posted.',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain="[('type', 'in', ('bank', 'cash'))]",
        tracking=True,
        help=(
            'Bank or cash journal for the accounting entry. '
            'If not set, the system selects a default based on '
            'payment method.'
        ),
    )
    account_payment_state = fields.Selection(
        related='account_payment_id.state',
        string='Acct. Payment Status',
        store=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Override: Post → create accounting entry
    # ═════════════════════════════════════════════════════════════════════════
    def action_post(self):
        """
        Extended post: after EMIS posting, create and post an
        ``account.payment`` and reconcile with related invoices.
        """
        result = super().action_post()
        for rec in self:
            rec._create_account_payment()
        return result

    def _create_account_payment(self):
        """
        Create an ``account.payment`` (inbound) for this EMIS payment
        and reconcile with the student's outstanding invoices.

        Silently skips accounting entry if:
          * no partner is determinable
          * no suitable journal is found

        Logs a message on the EMIS payment for traceability.
        """
        self.ensure_one()
        partner = self._get_payment_partner()
        if not partner:
            self.message_post(
                body='<em>Accounting entry skipped — no partner found.</em>',
                message_type='notification',
            )
            return

        journal = self.journal_id or self._get_default_payment_journal()
        if not journal:
            self.message_post(
                body=(
                    '<em>Accounting entry skipped — no payment journal '
                    'configured.</em>'
                ),
                message_type='notification',
            )
            return

        # Ensure partner is a customer
        if partner.customer_rank == 0:
            partner.sudo().write({'customer_rank': 1})

        # Determine currency
        currency = self.currency_id or self.env.company.currency_id

        payment_vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'amount': self.amount,
            'journal_id': journal.id,
            'date': self.payment_date,
            'ref': self.payment_no or '',
            'currency_id': currency.id,
        }

        account_payment = self.env['account.payment'].create(payment_vals)
        account_payment.action_post()
        self.account_payment_id = account_payment.id

        # Reconcile with related invoices
        self._reconcile_payment_with_invoices(account_payment)

        self.message_post(
            body=(
                f'<strong>Accounting payment created:</strong> '
                f'{account_payment.name}'
            ),
            message_type='notification',
        )

    def _reconcile_payment_with_invoices(self, account_payment):
        """
        Reconcile the ``account.payment`` with invoices linked to the
        allocated dues.

        Uses partial reconciliation when the payment amount doesn't
        fully cover the invoices.
        """
        # Collect unique posted invoices from allocated dues
        invoices = self.allocation_ids.mapped('due_id.invoice_id').filtered(
            lambda inv: (
                inv.state == 'posted'
                and inv.payment_state not in ('paid', 'reversed')
            )
        )
        if not invoices:
            return

        # Get receivable lines from the accounting payment
        payment_lines = account_payment.move_id.line_ids.filtered(
            lambda l: (
                l.account_id.account_type == 'asset_receivable'
                and not l.reconciled
            )
        )
        if not payment_lines:
            return

        # Get receivable lines from invoices
        invoice_lines = invoices.mapped('line_ids').filtered(
            lambda l: (
                l.account_id.account_type == 'asset_receivable'
                and not l.reconciled
            )
        )
        if not invoice_lines:
            return

        # Reconcile — Odoo handles partial automatically
        try:
            (payment_lines | invoice_lines).reconcile()
        except Exception:
            self.message_post(
                body=(
                    '<em>Auto-reconciliation failed. Manual '
                    'reconciliation may be needed.</em>'
                ),
                message_type='notification',
            )

    def _get_payment_partner(self):
        """Determine partner for accounting payment."""
        if self.student_id and self.student_id.partner_id:
            return self.student_id.partner_id
        if self.enrollment_id and self.enrollment_id.partner_id:
            return self.enrollment_id.partner_id
        return False

    def _get_default_payment_journal(self):
        """Find a default bank/cash journal based on payment method."""
        company = self.company_id or self.env.company
        jtype = 'cash' if self.payment_method == 'cash' else 'bank'
        return self.env['account.journal'].search([
            ('type', '=', jtype),
            ('company_id', '=', company.id),
        ], limit=1)

    # ═════════════════════════════════════════════════════════════════════════
    # Override: Cancel → reverse accounting entry
    # ═════════════════════════════════════════════════════════════════════════
    def action_cancel(self):
        """
        Extended cancel: also cancel the linked ``account.payment``.
        """
        result = super().action_cancel()
        for rec in self:
            rec._cancel_account_payment()
        return result

    def _cancel_account_payment(self):
        """
        Cancel the linked accounting payment.  Un-reconciles first
        if the payment was reconciled.
        """
        self.ensure_one()
        ap = self.account_payment_id
        if not ap:
            return
        if ap.state == 'posted':
            try:
                # Un-reconcile receivable lines
                rec_lines = ap.move_id.line_ids.filtered(
                    lambda l: l.reconciled
                )
                if rec_lines:
                    rec_lines.remove_move_reconcile()
                ap.action_draft()
                ap.action_cancel()
            except Exception:
                self.message_post(
                    body=(
                        '<em>Could not cancel accounting payment '
                        f'{ap.name}. Cancel it manually.</em>'
                    ),
                    message_type='notification',
                )

    # ═════════════════════════════════════════════════════════════════════════
    # Reset draft → also handle accounting
    # ═════════════════════════════════════════════════════════════════════════
    def action_reset_draft(self):
        """
        Extended reset: ensure accounting payment is cleaned up.
        """
        result = super().action_reset_draft()
        for rec in self:
            if rec.account_payment_id and \
                    rec.account_payment_id.state == 'cancelled':
                rec.account_payment_id = False
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Button
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_account_payment(self):
        self.ensure_one()
        if not self.account_payment_id:
            raise UserError('No accounting payment linked.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': self.account_payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
