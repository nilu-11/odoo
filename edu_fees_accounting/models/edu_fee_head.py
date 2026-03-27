from odoo import api, fields, models


class EduFeeHead(models.Model):
    """
    Stage 2 — Extend edu.fee.head with accounting integration fields.

    All new fields are optional so that existing fee head records
    continue to function without modification.  Accounting mapping is
    used only when generating invoices from student dues.

    Account resolution priority:
      1. Deposit nature → ``liability_account_id``
      2. Product's income account (via ``product_id``)
      3. ``income_account_id`` on this fee head
      4. Journal default (handled by Odoo when creating the invoice)
    """

    _inherit = 'edu.fee.head'

    # ── Accounting Integration Fields ─────────────────────────────────────
    product_id = fields.Many2one(
        'product.product',
        string='Accounting Product',
        tracking=True,
        help=(
            'Service product used on invoice lines for this fee head. '
            'If not set, the account below is used directly. '
            'Recommended: create one service product per major fee type.'
        ),
    )
    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        tracking=True,
        help=(
            'Revenue account for normal (non-deposit) fee invoicing. '
            'Falls back to the product\'s income account when not set.'
        ),
    )
    liability_account_id = fields.Many2one(
        'account.account',
        string='Deposit Liability Account',
        tracking=True,
        help=(
            'Current liability account for deposit fee invoicing. '
            'Used when fee_nature is "deposit".  The deposit is held '
            'as a liability until adjusted or refunded.'
        ),
    )
    tax_ids = fields.Many2many(
        'account.tax',
        'edu_fee_head_account_tax_rel',
        'fee_head_id',
        'tax_id',
        string='Customer Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
        help='Default taxes for invoice lines created from this fee head.',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Default analytic account for cost / revenue tracking.',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Account Resolution Helpers
    # ═════════════════════════════════════════════════════════════════════════
    def _get_invoice_account(self):
        """
        Return the correct ``account.account`` for an invoice line
        based on this fee head's nature and configuration.

        Resolution order:
          1. Deposit nature → ``liability_account_id``
          2. Product's income account
          3. ``income_account_id``
          4. Empty (Odoo uses journal default)
        """
        self.ensure_one()

        # Deposits always use the liability account
        if self.fee_nature == 'deposit' and self.liability_account_id:
            return self.liability_account_id

        # Try product income account
        if self.product_id:
            accounts = self.product_id.product_tmpl_id.get_product_accounts()
            if accounts.get('income'):
                return accounts['income']

        # Explicit income account on fee head
        if self.income_account_id:
            return self.income_account_id

        return self.env['account.account']

    def _get_invoice_taxes(self):
        """
        Return taxes for an invoice line, with fallback to
        product taxes.
        """
        self.ensure_one()
        if self.tax_ids:
            return self.tax_ids
        if self.product_id and self.product_id.taxes_id:
            return self.product_id.taxes_id
        return self.env['account.tax']

    def _get_analytic_distribution(self):
        """
        Return analytic distribution dict for invoice lines.
        Empty dict if no analytic account is configured.
        """
        self.ensure_one()
        if self.analytic_account_id:
            return {str(self.analytic_account_id.id): 100.0}
        return {}
