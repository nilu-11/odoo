from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduStudentPayment(models.Model):
    """
    Internal EMIS-level payment record — Stage 1.

    Tracks money received from a student and allocates it against one
    or more outstanding dues via allocation lines.

    Not an accounting entry — this is a billing-layer record that will
    later integrate with Odoo's account module in Stage 2.

    States:
        draft → posted → cancelled
    """

    _name = 'edu.student.payment'
    _description = 'Student Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    _rec_name = 'display_name'

    # ── Identity ──────────────────────────────────────────────────────────────
    payment_no = fields.Char(
        string='Payment No.',
        readonly=True,
        copy=False,
        index=True,
        help='Auto-assigned unique payment reference.',
    )

    # ── Linkage ───────────────────────────────────────────────────────────────
    enrollment_id = fields.Many2one(
        comodel_name='edu.enrollment',
        string='Enrollment',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    student_id = fields.Many2one(
        comodel_name='edu.student',
        string='Student',
        ondelete='set null',
        tracking=True,
        index=True,
    )
    applicant_profile_id = fields.Many2one(
        related='enrollment_id.applicant_profile_id',
        string='Applicant',
        store=True,
    )

    # ── Payment Details ───────────────────────────────────────────────────────
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='enrollment_id.currency_id',
        string='Currency',
        store=True,
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    reference = fields.Char(
        string='Reference',
        tracking=True,
        help='External reference — receipt number, bank reference, etc.',
    )
    payment_method = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('online', 'Online Payment'),
            ('other', 'Other'),
        ],
        string='Payment Method',
        default='cash',
        tracking=True,
    )

    # ── Allocation ────────────────────────────────────────────────────────────
    allocation_ids = fields.One2many(
        comodel_name='edu.student.payment.allocation',
        inverse_name='payment_id',
        string='Allocations',
    )
    allocated_amount = fields.Monetary(
        string='Allocated',
        currency_field='currency_id',
        compute='_compute_allocation_totals',
        store=True,
    )
    unallocated_amount = fields.Monetary(
        string='Unallocated',
        currency_field='currency_id',
        compute='_compute_allocation_totals',
        store=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # ── Convenience ───────────────────────────────────────────────────────────
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        related='enrollment_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── CRUD ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('payment_no'):
                vals['payment_no'] = (
                    seq.next_by_code('edu.student.payment') or '/'
                )
        return super().create(vals_list)

    # ── Display name ──────────────────────────────────────────────────────────
    @api.depends('payment_no', 'amount', 'payment_date')
    def _compute_display_name(self):
        for rec in self:
            no = rec.payment_no or 'Draft'
            rec.display_name = f'{no}'

    # ── Allocation totals ─────────────────────────────────────────────────────
    @api.depends('amount', 'allocation_ids.allocated_amount')
    def _compute_allocation_totals(self):
        for rec in self:
            allocated = sum(rec.allocation_ids.mapped('allocated_amount'))
            rec.allocated_amount = float_round(allocated, precision_digits=2)
            rec.unallocated_amount = float_round(
                rec.amount - allocated, precision_digits=2
            )

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if float_compare(rec.amount, 0.0, precision_digits=2) <= 0:
                raise ValidationError(
                    'Payment amount must be greater than zero.'
                )

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_post(self):
        """Draft → Posted.  Validates allocation totals and updates dues."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Only draft payments can be posted.')
            if float_compare(
                rec.allocated_amount, rec.amount, precision_digits=2
            ) > 0:
                raise UserError(
                    f'Allocated amount ({rec.allocated_amount}) exceeds '
                    f'payment amount ({rec.amount}).'
                )
        self.write({'state': 'posted'})
        # Update due states
        for rec in self:
            rec.allocation_ids.mapped('due_id')._update_state_from_payment()

    def action_cancel(self):
        """Posted or Draft → Cancelled.  Releases allocations on dues."""
        for rec in self:
            if rec.state == 'cancelled':
                raise UserError('Payment is already cancelled.')
        self.write({'state': 'cancelled'})
        # Recompute due states
        for rec in self:
            dues = rec.allocation_ids.mapped('due_id')
            if dues:
                dues._update_state_from_payment()

    def action_reset_draft(self):
        """Cancelled → Draft."""
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(
                    'Only cancelled payments can be reset to draft.'
                )
        self.write({'state': 'draft'})
        # Recompute due states
        for rec in self:
            dues = rec.allocation_ids.mapped('due_id')
            if dues:
                dues._update_state_from_payment()

    # ═════════════════════════════════════════════════════════════════════════
    # Payment Allocation
    # ═════════════════════════════════════════════════════════════════════════
    def action_allocate_payment(self):
        """
        Auto-allocate unallocated amount to outstanding dues for the
        same enrollment, oldest due first.

        Supports partial and multi-due allocation.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(
                'Automatic allocation is only available for draft payments.'
            )

        remaining = self.unallocated_amount
        if float_compare(remaining, 0.0, precision_digits=2) <= 0:
            raise UserError('No unallocated amount remaining.')

        # Find outstanding dues for this enrollment, ordered by due_date
        outstanding_dues = self.env['edu.student.fee.due'].search([
            ('enrollment_id', '=', self.enrollment_id.id),
            ('state', 'in', ['due', 'partial', 'overdue']),
            ('balance_amount', '>', 0),
        ], order='due_date asc, id asc')

        if not outstanding_dues:
            raise UserError('No outstanding dues found for this enrollment.')

        alloc_vals = []
        for due in outstanding_dues:
            if float_compare(remaining, 0.0, precision_digits=2) <= 0:
                break
            allocatable = min(remaining, due.balance_amount)
            alloc_vals.append({
                'payment_id': self.id,
                'due_id': due.id,
                'allocated_amount': float_round(
                    allocatable, precision_digits=2
                ),
            })
            remaining = float_round(
                remaining - allocatable, precision_digits=2
            )

        if alloc_vals:
            self.env['edu.student.payment.allocation'].create(alloc_vals)

        return True


class EduStudentPaymentAllocation(models.Model):
    """
    Links a portion of a payment to a specific due.

    Many-to-many bridge between payments and dues — a single payment
    can cover multiple dues, and a single due can receive allocations
    from multiple payments.
    """

    _name = 'edu.student.payment.allocation'
    _description = 'Payment Allocation'
    _order = 'payment_id, id'
    _rec_name = 'display_name'

    payment_id = fields.Many2one(
        comodel_name='edu.student.payment',
        string='Payment',
        required=True,
        ondelete='cascade',
        index=True,
    )
    due_id = fields.Many2one(
        comodel_name='edu.student.fee.due',
        string='Fee Due',
        required=True,
        ondelete='restrict',
        index=True,
    )
    allocated_amount = fields.Monetary(
        string='Allocated Amount',
        currency_field='currency_id',
        required=True,
    )

    # ── Convenience ───────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        related='payment_id.currency_id',
        string='Currency',
        store=True,
    )
    fee_head_id = fields.Many2one(
        related='due_id.fee_head_id',
        string='Fee Head',
        store=True,
    )
    company_id = fields.Many2one(
        related='payment_id.company_id',
        string='Company',
        store=True,
    )

    # ── Display name ──────────────────────────────────────────────────────────
    @api.depends('payment_id.payment_no', 'due_id.fee_head_id.name',
                 'allocated_amount')
    def _compute_display_name(self):
        for rec in self:
            pay = rec.payment_id.payment_no or ''
            head = rec.due_id.fee_head_id.name or ''
            rec.display_name = f'{pay} → {head}: {rec.allocated_amount}'

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('allocated_amount')
    def _check_allocated_amount(self):
        for rec in self:
            if float_compare(
                rec.allocated_amount, 0.0, precision_digits=2
            ) <= 0:
                raise ValidationError(
                    'Allocated amount must be greater than zero.'
                )

    @api.constrains('payment_id', 'allocated_amount')
    def _check_allocation_not_exceeds_payment(self):
        """Total allocations must not exceed the payment amount."""
        for rec in self:
            payment = rec.payment_id
            total_alloc = sum(
                payment.allocation_ids.mapped('allocated_amount')
            )
            if float_compare(
                total_alloc, payment.amount, precision_digits=2
            ) > 0:
                raise ValidationError(
                    f'Total allocations ({total_alloc}) exceed '
                    f'payment amount ({payment.amount}) for '
                    f'"{payment.payment_no}".'
                )

    @api.constrains('due_id', 'allocated_amount')
    def _check_allocation_not_exceeds_due(self):
        """Total allocations on a due must not exceed its due amount."""
        for rec in self:
            due = rec.due_id
            total_alloc = sum(
                due.allocation_ids.mapped('allocated_amount')
            )
            if float_compare(
                total_alloc, due.due_amount, precision_digits=2
            ) > 0:
                raise ValidationError(
                    f'Total allocations ({total_alloc}) exceed '
                    f'due amount ({due.due_amount}) for '
                    f'"{due.display_name}".'
                )
