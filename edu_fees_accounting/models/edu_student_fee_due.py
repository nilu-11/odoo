from odoo import api, fields, models, Command
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round


class EduStudentFeeDue(models.Model):
    """
    Stage 2 — Extend student fee due with accounting integration.

    Adds:
      * invoice link and invoice-generation workflow
      * credit-note link and creation
      * financial-state synchronisation with Accounting
      * cron method for overdue / state sync
    """

    _inherit = 'edu.student.fee.due'

    # ═════════════════════════════════════════════════════════════════════════
    # Invoice Link
    # ═════════════════════════════════════════════════════════════════════════
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        ondelete='set null',
        index=True,
        copy=False,
        tracking=True,
        help='Customer invoice generated from this due.',
    )
    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Invoice Status',
        store=True,
    )
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state',
        string='Invoice Payment',
        store=True,
    )
    amount_invoiced = fields.Monetary(
        string='Amount Invoiced',
        currency_field='currency_id',
        default=0.0,
        copy=False,
        help='Amount included on the linked invoice.',
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Credit Note Link
    # ═════════════════════════════════════════════════════════════════════════
    credit_note_id = fields.Many2one(
        'account.move',
        string='Credit Note',
        ondelete='set null',
        copy=False,
        tracking=True,
    )

    # ═════════════════════════════════════════════════════════════════════════
    # Invoice Generation
    # ═════════════════════════════════════════════════════════════════════════
    def action_create_invoice_from_dues(self):
        """
        Create customer invoices from the selected dues.

        Groups dues by enrollment (one invoice per enrollment/student).
        Each due becomes one invoice line using the fee head's product
        and account mapping.

        Returns an action to view the created invoice(s).
        """
        if not self:
            raise UserError('No dues selected.')

        # ── Validations ──
        for due in self:
            if due.invoice_id:
                raise UserError(
                    f'Due "{due.display_name}" is already invoiced '
                    f'(Invoice: {due.invoice_id.name}). '
                    'Create a credit note to reverse it first.'
                )
            if due.state == 'draft':
                raise UserError(
                    f'Due "{due.display_name}" is in draft state. '
                    'Set it to "due" before invoicing.'
                )
            if float_compare(due.due_amount, 0.0, precision_digits=2) <= 0:
                raise UserError(
                    f'Due "{due.display_name}" has no positive amount '
                    'to invoice.'
                )

        # ── Group by enrollment ──
        grouped = {}
        for due in self:
            key = due.enrollment_id.id
            grouped.setdefault(key, self.env['edu.student.fee.due'])
            grouped[key] |= due

        # ── Create invoices ──
        invoices = self.env['account.move']
        for _enrollment_id, dues in grouped.items():
            invoice = dues._create_invoice_for_dues()
            invoices |= invoice

        # ── Return action ──
        if len(invoices) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': invoices.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Student Fee Invoices',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
        }

    def _create_invoice_for_dues(self):
        """
        Create a single ``account.move`` (out_invoice) for a set of
        dues belonging to the same enrollment.

        Returns the created (draft) invoice.
        """
        enrollment = self[0].enrollment_id
        partner = self._get_invoice_partner()
        company = enrollment.company_id or self.env.company

        # Ensure partner is flagged as customer
        if partner.customer_rank == 0:
            partner.sudo().write({'customer_rank': 1})

        # Find sale journal
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not journal:
            raise UserError(
                'No sale journal found for company '
                f'"{company.name}". Configure one in Accounting first.'
            )

        # Build invoice lines
        invoice_line_vals = []
        for due in self:
            fee_head = due.fee_head_id
            account = fee_head._get_invoice_account()
            taxes = fee_head._get_invoice_taxes()
            analytic = fee_head._get_analytic_distribution()

            line_vals = {
                'name': f'{fee_head.name} — {due.display_name}',
                'quantity': 1,
                'price_unit': due.due_amount,
            }
            if fee_head.product_id:
                line_vals['product_id'] = fee_head.product_id.id
            if account:
                line_vals['account_id'] = account.id
            if taxes:
                line_vals['tax_ids'] = [Command.set(taxes.ids)]
            if analytic:
                line_vals['analytic_distribution'] = analytic

            invoice_line_vals.append(Command.create(line_vals))

        # Determine currency
        currency = self[0].currency_id or company.currency_id

        # Create the invoice
        enrollment_ref = enrollment.enrollment_no or str(enrollment.id)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'journal_id': journal.id,
            'currency_id': currency.id,
            'invoice_origin': f'EDU-FEE/{enrollment_ref}',
            'ref': f'Student Fee — {enrollment_ref}',
            'invoice_line_ids': invoice_line_vals,
            'company_id': company.id,
        })

        # Link dues to invoice
        for due in self:
            due.write({
                'invoice_id': invoice.id,
                'amount_invoiced': due.due_amount,
            })

        return invoice

    def _get_invoice_partner(self):
        """Determine the res.partner for invoicing this group of dues."""
        due = self[0]
        if due.student_id and due.student_id.partner_id:
            return due.student_id.partner_id
        if due.enrollment_id and due.enrollment_id.partner_id:
            return due.enrollment_id.partner_id
        raise UserError(
            f'Cannot determine invoice partner for due '
            f'"{due.display_name}". Ensure the student or '
            'enrollment has a partner contact.'
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Credit Note
    # ═════════════════════════════════════════════════════════════════════════
    def action_create_credit_note(self):
        """
        Create credit notes (``out_refund``) for selected dues that
        were invoiced incorrectly or need post-invoice correction.

        One credit note per due.  Returns an action to view the
        created credit note(s).
        """
        if not self:
            raise UserError('No dues selected.')

        for due in self:
            if not due.invoice_id:
                raise UserError(
                    f'Due "{due.display_name}" has no linked invoice. '
                    'Cannot create a credit note.'
                )
            if due.invoice_id.state != 'posted':
                raise UserError(
                    f'Invoice "{due.invoice_id.name}" must be posted '
                    'before a credit note can be created.'
                )
            if due.credit_note_id:
                raise UserError(
                    f'A credit note already exists for '
                    f'"{due.display_name}": {due.credit_note_id.name}.'
                )

        credit_notes = self.env['account.move']
        for due in self:
            cn = due._create_single_credit_note()
            credit_notes |= cn

        if len(credit_notes) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': credit_notes.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Notes',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', credit_notes.ids)],
        }

    def _create_single_credit_note(self):
        """Create a credit note for a single due."""
        self.ensure_one()
        fee_head = self.fee_head_id
        account = fee_head._get_invoice_account()
        taxes = fee_head._get_invoice_taxes()
        analytic = fee_head._get_analytic_distribution()

        partner = self._get_invoice_partner()
        company = self.company_id or self.env.company
        enrollment_ref = self.enrollment_id.enrollment_no or ''

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not journal:
            raise UserError('No sale journal found.')

        credit_amount = self.amount_invoiced or self.due_amount

        line_vals = {
            'name': f'Credit: {fee_head.name} — {self.display_name}',
            'quantity': 1,
            'price_unit': credit_amount,
        }
        if fee_head.product_id:
            line_vals['product_id'] = fee_head.product_id.id
        if account:
            line_vals['account_id'] = account.id
        if taxes:
            line_vals['tax_ids'] = [Command.set(taxes.ids)]
        if analytic:
            line_vals['analytic_distribution'] = analytic

        cn_vals = {
            'move_type': 'out_refund',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'journal_id': journal.id,
            'currency_id': (
                self.currency_id.id or company.currency_id.id
            ),
            'ref': f'Credit Note — {self.display_name}',
            'invoice_origin': f'EDU-CN/{enrollment_ref}',
            'invoice_line_ids': [Command.create(line_vals)],
            'company_id': company.id,
        }
        # Link to original invoice if possible
        if self.invoice_id:
            cn_vals['reversed_entry_id'] = self.invoice_id.id

        credit_note = self.env['account.move'].create(cn_vals)
        self.write({
            'credit_note_id': credit_note.id,
            'amount_invoiced': 0.0,
        })
        return credit_note

    # ═════════════════════════════════════════════════════════════════════════
    # Financial State Synchronisation
    # ═════════════════════════════════════════════════════════════════════════
    def action_sync_due_financial_status(self):
        """
        Synchronise EMIS due state with Accounting invoice status.

        Call manually or via cron.  Logic:
          * invoice fully reconciled (payment_state='paid') → due = paid
          * invoice partially paid → due = partial
          * invoice posted + past due_date with balance → due = overdue
          * invoice posted + within due_date → due = due
          * no invoice → fall back to allocation-based state
        """
        today = fields.Date.context_today(self)
        for due in self:
            if due.state == 'draft':
                continue

            # If invoice exists, use invoice payment state as truth
            if due.invoice_id and due.invoice_id.state == 'posted':
                inv = due.invoice_id
                pstate = inv.payment_state or 'not_paid'

                if pstate in ('paid', 'in_payment', 'reversed'):
                    if due.state != 'paid':
                        due.state = 'paid'
                elif pstate == 'partial':
                    if due.state not in ('partial', 'overdue'):
                        due.state = 'partial'
                    # Check overdue
                    if (due.due_date and due.due_date < today
                            and due.state != 'overdue'):
                        due.state = 'overdue'
                else:
                    # Not paid
                    if due.due_date and due.due_date < today:
                        if due.state != 'overdue':
                            due.state = 'overdue'
                    elif due.state not in ('due',):
                        due.state = 'due'
            else:
                # No invoice — use allocation-based state (Stage 1)
                due._update_state_from_payment()

                # Additionally mark overdue by date
                if (due.state in ('due', 'partial')
                        and due.due_date
                        and due.due_date < today):
                    due.state = 'overdue'

    # ── Cron entry point ──────────────────────────────────────────────────
    @api.model
    def cron_sync_financial_status(self):
        """
        Scheduled action: sync all non-draft, non-paid dues.
        """
        dues = self.search([
            ('state', 'not in', ('draft', 'paid')),
        ])
        dues.action_sync_due_financial_status()
        return True

    # ═════════════════════════════════════════════════════════════════════════
    # Smart Button Helpers
    # ═════════════════════════════════════════════════════════════════════════
    def action_view_invoice(self):
        """Open the linked invoice."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError('No invoice linked to this due.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_credit_note(self):
        """Open the linked credit note."""
        self.ensure_one()
        if not self.credit_note_id:
            raise UserError('No credit note linked to this due.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.credit_note_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
