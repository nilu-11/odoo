from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduAdmissionRegister(models.Model):
    """
    Admission Register — represents an admission opening/intake configuration
    for a specific program + academic year + optional batch scope.

    Each register resolves its fee structure and payment plans from the
    edu_fees_structure module, following a batch-specific → program-level
    fallback strategy.
    """

    _name = 'edu.admission.register'
    _description = 'Admission Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_id, id desc'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Register Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Code',
        readonly=True,
        copy=False,
        help='Auto-assigned unique reference code.',
    )

    # ── Academic Scope ────────────────────────────────────────────────────────
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        default=lambda self: self.env['edu.academic.year']._get_current_year(),
    )
    program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Batch',
        ondelete='restrict',
        tracking=True,
        index=True,
        domain="[('program_id', '=', program_id), "
               "('academic_year_id', '=', academic_year_id)]",
        help='Optional batch-level scope. Leave empty for program-wide register.',
    )
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    application_start_date = fields.Date(
        string='Application Start Date',
        tracking=True,
    )
    application_end_date = fields.Date(
        string='Application End Date',
        tracking=True,
    )

    # ── Capacity ──────────────────────────────────────────────────────────────
    seat_limit = fields.Integer(
        string='Seat Limit',
        default=0,
        help='Maximum number of seats. 0 = unlimited.',
    )
    available_seat_count = fields.Integer(
        string='Available Seats',
        compute='_compute_available_seat_count',
    )

    # ── Fee Integration ───────────────────────────────────────────────────────
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        ondelete='restrict',
        tracking=True,
        help='Resolved fee structure. Auto-fetched on scope change, or set manually.',
    )
    available_payment_plan_ids = fields.Many2many(
        comodel_name='edu.fee.payment.plan',
        relation='edu_admission_register_payment_plan_rel',
        column1='register_id',
        column2='plan_id',
        string='Available Payment Plans',
        help='Payment plans available for applicants in this register.',
    )
    default_payment_plan_id = fields.Many2one(
        comodel_name='edu.fee.payment.plan',
        string='Default Payment Plan',
        ondelete='set null',
        help='Pre-selected payment plan for new applications.',
    )

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    # ── Flow Configuration ─────────────────────────────────────
    flow_preset = fields.Selection(
        [
            ('fast_track', 'Fast Track'),
            ('standard', 'Standard'),
            ('full', 'Full'),
            ('custom', 'Custom'),
        ],
        string='Admission Flow',
        default='standard',
        required=True,
        tracking=True,
        help="Controls which stages applications in this register go through.",
    )
    require_academic_review = fields.Boolean(
        string='Require Academic Review',
        default=True,
        tracking=True,
        help="If disabled, applications skip the review stage and go directly to approval.",
    )
    require_scholarship_review = fields.Boolean(
        string='Require Scholarship Review',
        default=False,
        tracking=True,
        help="If enabled, scholarship review is required before approval.",
    )
    require_offer_letter = fields.Boolean(
        string='Require Offer Letter',
        default=True,
        tracking=True,
        help="If enabled, an offer letter must be generated before enrollment.",
    )
    require_odoo_sign = fields.Boolean(
        string='Require Digital Signature',
        default=False,
        tracking=True,
        help="If enabled, offer letter must be signed via Odoo Sign before enrollment.",
    )
    require_payment_confirmation = fields.Boolean(
        string='Require Payment Confirmation',
        default=True,
        tracking=True,
        help="If enabled, payment must be confirmed before enrollment.",
    )
    sign_template_id = fields.Many2one(
        'sign.template',
        string='Offer Letter Sign Template',
        ondelete='set null',
        help="Odoo Sign template used for offer letter digital signatures.",
    )
    sign_module_installed = fields.Boolean(
        compute='_compute_sign_module_installed',
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    application_ids = fields.One2many(
        comodel_name='edu.admission.application',
        inverse_name='admission_register_id',
        string='Applications',
    )
    application_count = fields.Integer(
        string='Applications',
        compute='_compute_application_count',
        store=True,
    )
    submitted_count = fields.Integer(
        string='Submitted',
        compute='_compute_application_state_counts',
    )
    under_review_count = fields.Integer(
        string='Under Review',
        compute='_compute_application_state_counts',
    )
    offered_count = fields.Integer(
        string='Offered',
        compute='_compute_application_state_counts',
    )
    enrolled_count = fields.Integer(
        string='Enrolled',
        compute='_compute_application_state_counts',
    )
    cancelled_count = fields.Integer(
        string='Cancelled',
        compute='_compute_application_state_counts',
    )

    # ── Company ───────────────────────────────────────────────────────────────
    company_id = fields.Many2one(
        related='program_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── SQL Constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Register code must be unique.'),
    ]

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = seq.next_by_code('edu.admission.register') or '/'
        return super().create(vals_list)

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('application_ids')
    def _compute_application_count(self):
        data = self.env['edu.admission.application']._read_group(
            [('admission_register_id', 'in', self.ids)],
            ['admission_register_id'],
            ['__count'],
        )
        mapped = {r.id: count for r, count in data}
        for rec in self:
            rec.application_count = mapped.get(rec.id, 0)

    @api.depends('application_ids.state')
    def _compute_application_state_counts(self):
        STATE_FIELDS = {
            'submitted': 'submitted_count',
            'under_review': 'under_review_count',
            'offered': 'offered_count',
            'enrolled': 'enrolled_count',
            'cancelled': 'cancelled_count',
        }
        if not self.ids:
            for rec in self:
                for fname in STATE_FIELDS.values():
                    setattr(rec, fname, 0)
            return
        data = self.env['edu.admission.application']._read_group(
            [
                ('admission_register_id', 'in', self.ids),
                ('state', 'in', list(STATE_FIELDS.keys())),
            ],
            ['admission_register_id', 'state'],
            ['__count'],
        )
        # {register_id: {state: count}}
        mapped = {}
        for register, state, count in data:
            mapped.setdefault(register.id, {})[state] = count
        for rec in self:
            counts = mapped.get(rec.id, {})
            for state_key, fname in STATE_FIELDS.items():
                setattr(rec, fname, counts.get(state_key, 0))

    def _compute_available_seat_count(self):
        data = self.env['edu.admission.application']._read_group(
            [
                ('admission_register_id', 'in', self.ids),
                ('state', 'not in', ['cancelled']),
            ],
            ['admission_register_id'],
            ['__count'],
        )
        mapped = {r.id: count for r, count in data}
        for rec in self:
            if rec.seat_limit > 0:
                rec.available_seat_count = max(
                    0, rec.seat_limit - mapped.get(rec.id, 0)
                )
            else:
                rec.available_seat_count = -1  # unlimited

    # ── Fee Structure Resolution ──────────────────────────────────────────────
    def _resolve_fee_structure(self):
        """
        Resolve fee structure for this register's academic scope.

        Strategy:
        1. Batch-specific structure (if batch is set)
        2. Fallback to program-level structure (batch_id = False)
        3. Return False if none found
        """
        self.ensure_one()
        FeeStructure = self.env['edu.fee.structure']
        # Try batch-specific first
        if self.batch_id:
            structure = FeeStructure.search([
                ('program_id', '=', self.program_id.id),
                ('academic_year_id', '=', self.academic_year_id.id),
                ('batch_id', '=', self.batch_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if structure:
                return structure
        # Fallback to generic program-level
        structure = FeeStructure.search([
            ('program_id', '=', self.program_id.id),
            ('academic_year_id', '=', self.academic_year_id.id),
            ('batch_id', '=', False),
            ('state', '=', 'active'),
        ], limit=1)
        return structure or self.env['edu.fee.structure']

    def _load_payment_plans_from_structure(self):
        """Load payment plans from the resolved fee structure."""
        self.ensure_one()
        if self.fee_structure_id and self.fee_structure_id.payment_plan_ids:
            self.available_payment_plan_ids = [
                (6, 0, self.fee_structure_id.payment_plan_ids.ids)
            ]
            # Set default plan to the first if not already set
            if (
                not self.default_payment_plan_id
                or self.default_payment_plan_id
                not in self.fee_structure_id.payment_plan_ids
            ):
                self.default_payment_plan_id = (
                    self.fee_structure_id.payment_plan_ids[0].id
                )
        else:
            self.available_payment_plan_ids = [(5, 0, 0)]
            self.default_payment_plan_id = False

    # ── Flow Preset Map ───────────────────────────────────────────────────────
    _PRESET_MAP = {
        'fast_track': {
            'require_academic_review': False,
            'require_scholarship_review': False,
            'require_offer_letter': False,
            'require_odoo_sign': False,
            'require_payment_confirmation': False,
        },
        'standard': {
            'require_academic_review': True,
            'require_scholarship_review': False,
            'require_offer_letter': True,
            'require_odoo_sign': False,
            'require_payment_confirmation': True,
        },
        'full': {
            'require_academic_review': True,
            'require_scholarship_review': True,
            'require_offer_letter': True,
            'require_odoo_sign': True,
            'require_payment_confirmation': True,
        },
    }

    # ── Computed ──────────────────────────────────────────────────────────────
    def _compute_sign_module_installed(self):
        installed = bool(self.env['ir.module.module'].sudo().search(
            [('name', '=', 'sign'), ('state', '=', 'installed')], limit=1
        ))
        for rec in self:
            rec.sign_module_installed = installed

    # ── Onchange ──────────────────────────────────────────────────────────────
    @api.onchange('flow_preset')
    def _onchange_flow_preset(self):
        preset_vals = self._PRESET_MAP.get(self.flow_preset)
        if preset_vals:
            for field_name, value in preset_vals.items():
                setattr(self, field_name, value)

    @api.onchange('program_id', 'academic_year_id')
    def _onchange_academic_scope(self):
        """Clear batch if it no longer matches the new program/year."""
        if self.batch_id and (
            self.batch_id.program_id != self.program_id
            or self.batch_id.academic_year_id != self.academic_year_id
        ):
            self.batch_id = False

    @api.onchange('program_id', 'academic_year_id', 'batch_id')
    def _onchange_resolve_fee_structure(self):
        """Auto-resolve fee structure when scope changes."""
        if self.program_id and self.academic_year_id:
            structure = self._resolve_fee_structure()
            self.fee_structure_id = structure.id if structure else False
        else:
            self.fee_structure_id = False

    @api.onchange('fee_structure_id')
    def _onchange_fee_structure(self):
        """Reload payment plans when fee structure changes."""
        self._load_payment_plans_from_structure()

    # ── Python Constraints ────────────────────────────────────────────────────
    @api.constrains('application_start_date', 'application_end_date')
    def _check_date_range(self):
        for rec in self:
            if (
                rec.application_start_date
                and rec.application_end_date
                and rec.application_start_date > rec.application_end_date
            ):
                raise ValidationError(
                    'Application start date must be before end date.'
                )

    @api.constrains('batch_id', 'program_id', 'academic_year_id')
    def _check_batch_scope(self):
        for rec in self:
            if not rec.batch_id:
                continue
            if rec.batch_id.program_id != rec.program_id:
                raise ValidationError(
                    f'Batch "{rec.batch_id.name}" does not belong to '
                    f'program "{rec.program_id.name}".'
                )
            if rec.batch_id.academic_year_id != rec.academic_year_id:
                raise ValidationError(
                    f'Batch "{rec.batch_id.name}" does not belong to '
                    f'academic year "{rec.academic_year_id.name}".'
                )

    @api.constrains('default_payment_plan_id', 'available_payment_plan_ids')
    def _check_default_plan_in_available(self):
        for rec in self:
            if (
                rec.default_payment_plan_id
                and rec.default_payment_plan_id
                not in rec.available_payment_plan_ids
            ):
                raise ValidationError(
                    'Default payment plan must be one of the available plans.'
                )

    # ── Write Locking ─────────────────────────────────────────────────────────
    _SCOPE_FIELDS = frozenset({
        'program_id', 'academic_year_id', 'batch_id', 'department_id',
    })

    def write(self, vals):
        if self._SCOPE_FIELDS & vals.keys():
            for rec in self:
                if rec.application_count > 0:
                    raise UserError(
                        f'Cannot change academic scope on register '
                        f'"{rec.name}" — it has {rec.application_count} '
                        f'application(s). Close or cancel them first.'
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.application_count > 0:
                raise UserError(
                    f'Cannot delete register "{rec.name}" — '
                    f'it has {rec.application_count} application(s).'
                )
        return super().unlink()

    # ── State Transitions ─────────────────────────────────────────────────────
    def action_open(self):
        for rec in self:
            if not rec.fee_structure_id:
                raise UserError(
                    f'Cannot open register "{rec.name}" — '
                    'no fee structure is resolved. Configure the academic scope '
                    'and ensure an active fee structure exists.'
                )
            if not rec.program_id or not rec.academic_year_id:
                raise UserError(
                    f'Cannot open register "{rec.name}" — '
                    'program and academic year are required.'
                )
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(
            lambda r: r.state in ('closed', 'cancelled')
        ).write({'state': 'draft'})

    # ── Smart Buttons ─────────────────────────────────────────────────────────
    def _action_view_applications_by_state(self, state, name):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{name} — {self.name}',
            'res_model': 'edu.admission.application',
            'view_mode': 'list,form',
            'domain': [
                ('admission_register_id', '=', self.id),
                ('state', '=', state),
            ],
            'context': {'default_admission_register_id': self.id},
        }

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Applications — {self.name}',
            'res_model': 'edu.admission.application',
            'view_mode': 'list,form',
            'domain': [('admission_register_id', '=', self.id)],
            'context': {'default_admission_register_id': self.id},
        }

    def action_view_submitted(self):
        return self._action_view_applications_by_state('submitted', 'Submitted')

    def action_view_under_review(self):
        return self._action_view_applications_by_state('under_review', 'Under Review')

    def action_view_offered(self):
        return self._action_view_applications_by_state('offered', 'Offered')

    def action_view_enrolled(self):
        return self._action_view_applications_by_state('enrolled', 'Enrolled')

    def action_view_cancelled(self):
        return self._action_view_applications_by_state('cancelled', 'Cancelled')

    def action_start_application(self):
        """Open a blank application form with all scope & fee context pre-filled."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(
                f'Cannot start an application — register "{self.name}" is not open.'
            )
        ctx = {
            'default_admission_register_id': self.id,
            'default_program_id': self.program_id.id,
            'default_academic_year_id': self.academic_year_id.id,
            'default_fee_structure_id': (
                self.fee_structure_id.id if self.fee_structure_id else False
            ),
            'default_selected_payment_plan_id': (
                self.default_payment_plan_id.id
                if self.default_payment_plan_id else False
            ),
        }
        if self.batch_id:
            ctx['default_batch_id'] = self.batch_id.id
        if self.available_payment_plan_ids:
            ctx['default_available_payment_plan_ids'] = [
                (6, 0, self.available_payment_plan_ids.ids)
            ]
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Application',
            'res_model': 'edu.admission.application',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
