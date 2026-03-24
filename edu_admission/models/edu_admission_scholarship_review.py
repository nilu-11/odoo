from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_round


class EduAdmissionScholarshipReview(models.Model):
    """
    Structured per-application scholarship assessment / decision record.

    Each line references a scholarship scheme and captures:
    - Recommended values (officer proposal)
    - Approved values (final decision)
    - Snapshot of scheme rules at approval time for audit stability

    An application may have multiple review lines for different schemes.
    """

    _name = 'edu.admission.scholarship.review'
    _description = 'Admission Scholarship Review'
    _order = 'sequence, id'
    _rec_name = 'display_name'

    # ── Identity ──────────────────────────────────────────────────────────────
    application_id = fields.Many2one(
        comodel_name='edu.admission.application',
        string='Application',
        required=True,
        ondelete='cascade',
        index=True,
    )
    scholarship_scheme_id = fields.Many2one(
        comodel_name='edu.scholarship.scheme',
        string='Scholarship Scheme',
        required=True,
        ondelete='restrict',
        index=True,
    )
    sequence = fields.Integer(
        string='Priority',
        default=10,
        help='Lower number = higher priority. Controls calculation order.',
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('under_review', 'Under Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    # ── Recommendation (officer proposal) ─────────────────────────────────────
    recommendation_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed Amount'),
            ('full', 'Full Scholarship'),
        ],
        string='Recommendation Type',
    )
    recommended_percent = fields.Float(
        string='Recommended %',
        digits=(5, 2),
    )
    recommended_amount = fields.Float(
        string='Recommended Amount',
        digits=(12, 2),
    )

    # ── Approved (final decision) ─────────────────────────────────────────────
    approved_type = fields.Selection(
        selection=[
            ('percentage', 'Percentage'),
            ('fixed', 'Fixed Amount'),
            ('full', 'Full Scholarship'),
        ],
        string='Approved Type',
    )
    approved_percent = fields.Float(
        string='Approved %',
        digits=(5, 2),
    )
    approved_amount = fields.Float(
        string='Approved Amount',
        digits=(12, 2),
    )

    # ── Calculated ────────────────────────────────────────────────────────────
    calculated_discount_amount = fields.Float(
        string='Calculated Discount',
        digits=(12, 2),
        help='Final calculated discount after caps and stacking logic.',
    )
    cap_applied = fields.Boolean(
        string='Cap Applied',
        default=False,
    )

    # ── Snapshots (frozen at approval time) ───────────────────────────────────
    priority_snapshot = fields.Integer(string='Priority (Snapshot)')
    exclusive_snapshot = fields.Boolean(string='Exclusive (Snapshot)')
    stacking_allowed_snapshot = fields.Boolean(string='Stacking Allowed (Snapshot)')
    eligibility_basis_snapshot = fields.Char(string='Eligibility Basis (Snapshot)')
    applies_on_snapshot = fields.Char(string='Applies On (Snapshot)')

    # ── Audit ─────────────────────────────────────────────────────────────────
    remarks = fields.Text(string='Remarks')
    approved_by = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
    )

    # ── System ────────────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        related='application_id.company_id',
        string='Company',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='application_id.currency_id',
        string='Currency',
    )

    # ── Display Name ──────────────────────────────────────────────────────────
    @api.depends('application_id.application_no', 'scholarship_scheme_id.name')
    def _compute_display_name(self):
        for rec in self:
            app_no = rec.application_id.application_no or 'New'
            scheme = rec.scholarship_scheme_id.name or 'No Scheme'
            rec.display_name = f'{app_no} / {scheme}'

    # ── Constraints ───────────────────────────────────────────────────────────
    @api.constrains('approved_percent')
    def _check_approved_percent(self):
        for rec in self:
            if rec.approved_percent < 0 or rec.approved_percent > 100:
                raise ValidationError(
                    'Approved percentage must be between 0 and 100.'
                )

    @api.constrains('approved_amount')
    def _check_approved_amount(self):
        for rec in self:
            if rec.approved_amount < 0:
                raise ValidationError('Approved amount cannot be negative.')

    @api.constrains('recommended_percent')
    def _check_recommended_percent(self):
        for rec in self:
            if rec.recommended_percent < 0 or rec.recommended_percent > 100:
                raise ValidationError(
                    'Recommended percentage must be between 0 and 100.'
                )

    _sql_constraints = [
        (
            'unique_application_scheme',
            'UNIQUE(application_id, scholarship_scheme_id)',
            'Only one review line per scholarship scheme per application.',
        ),
    ]

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('scholarship_scheme_id')
    def _onchange_scheme(self):
        """Pre-fill recommendation from scheme defaults."""
        scheme = self.scholarship_scheme_id
        if scheme:
            self.sequence = scheme.priority
            self.recommendation_type = (
                'full' if scheme.award_type == 'full'
                else scheme.award_type if scheme.award_type in ('percentage', 'fixed')
                else 'percentage'
            )
            if scheme.award_type == 'percentage':
                self.recommended_percent = scheme.default_percent
            elif scheme.award_type == 'fixed':
                self.recommended_amount = scheme.default_amount
            elif scheme.award_type == 'full':
                self.recommended_percent = 100.0

    # ── Write Locking ─────────────────────────────────────────────────────────
    def write(self, vals):
        for rec in self:
            if (
                rec.application_id.state
                in rec.application_id._FROZEN_STATES
                and rec.state == 'approved'
            ):
                raise UserError(
                    f'Cannot modify approved scholarship review for '
                    f'"{rec.application_id.application_no}" — '
                    'the application is frozen after offer acceptance.'
                )
        return super().write(vals)

    # ── Discount Calculation ──────────────────────────────────────────────────
    def _calculate_raw_discount(self, eligible_total):
        """
        Calculate raw discount amount from approved values.
        Does not apply caps — that is done by the application.
        """
        self.ensure_one()
        if self.approved_type == 'full':
            return eligible_total
        elif self.approved_type == 'percentage':
            return float_round(
                eligible_total * (self.approved_percent or 0.0) / 100.0,
                precision_digits=2,
            )
        elif self.approved_type == 'fixed':
            return self.approved_amount or 0.0
        return 0.0

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_start_review(self):
        self.filtered(
            lambda r: r.state == 'draft'
        ).write({'state': 'under_review'})

    def action_approve(self):
        """
        Approve this scholarship review line.
        Snapshots scheme rules and calculates the discount.
        """
        for rec in self:
            if rec.state not in ('draft', 'under_review'):
                raise UserError(
                    f'Cannot approve review in "{rec.state}" state.'
                )
            if not rec.approved_type:
                raise UserError(
                    'Set an approved type (percentage/fixed/full) before approving.'
                )
            scheme = rec.scholarship_scheme_id
            # Snapshot scheme rules at approval time
            rec.write({
                'state': 'approved',
                'approved_by': self.env.uid,
                'approval_date': fields.Datetime.now(),
                'priority_snapshot': scheme.priority,
                'exclusive_snapshot': scheme.exclusive,
                'stacking_allowed_snapshot': scheme.allow_stacking,
                'eligibility_basis_snapshot': scheme.eligibility_basis,
                'applies_on_snapshot': scheme.applies_on,
            })
        # Trigger scholarship recalc on parent applications
        applications = self.mapped('application_id')
        for app in applications:
            if app.state not in app._FROZEN_STATES:
                app._recompute_scholarship_summary()

    def action_reject(self):
        for rec in self:
            if rec.state in ('cancelled',):
                raise UserError('Cannot reject a cancelled review.')
        self.write({'state': 'rejected'})
        # Trigger scholarship recalc
        applications = self.mapped('application_id')
        for app in applications:
            if app.state not in app._FROZEN_STATES:
                app._recompute_scholarship_summary()

    def action_cancel(self):
        self.write({
            'state': 'cancelled',
            'calculated_discount_amount': 0.0,
        })
        applications = self.mapped('application_id')
        for app in applications:
            if app.state not in app._FROZEN_STATES:
                app._recompute_scholarship_summary()

    def action_reset_draft(self):
        for rec in self:
            if rec.application_id.state in rec.application_id._FROZEN_STATES:
                raise UserError(
                    'Cannot reset scholarship review — '
                    'application is frozen after offer acceptance.'
                )
        self.write({
            'state': 'draft',
            'approved_by': False,
            'approval_date': False,
            'calculated_discount_amount': 0.0,
            'cap_applied': False,
            'priority_snapshot': 0,
            'exclusive_snapshot': False,
            'stacking_allowed_snapshot': False,
            'eligibility_basis_snapshot': False,
            'applies_on_snapshot': False,
        })
