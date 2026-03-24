from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduFeeStructure(models.Model):
    _name = 'edu.fee.structure'
    _description = 'Fee Structure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_id, name'
    _rec_name = 'name'

    # ── Identity ────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Structure Name',
        required=True,
        tracking=True,
        help='E.g. BCA Fee Structure 2026 Intake, Grade 11 Science 2026',
    )
    code = fields.Char(
        string='Code',
        readonly=True,
        copy=False,
        help='Auto-assigned unique reference code.',
    )

    # ── Scope ────────────────────────────────────────────────────────────────────
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Intake Year',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help=(
            'The academic year in which students are admitted under this fee plan. '
            'This is the cohort/intake year — fee lines may span multiple '
            'subsequent academic years across all progression stages.'
        ),
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
        string='Batch (Optional)',
        ondelete='restrict',
        tracking=True,
        index=True,
        help=(
            'Leave empty for a general program-level fee structure. '
            'Fill to create a batch-specific override. '
            'Batch must belong to the selected program and intake year.'
        ),
    )

    # ── Financial ────────────────────────────────────────────────────────────────
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )

    # ── State ────────────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    # ── Lines ─────────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        comodel_name='edu.fee.structure.line',
        inverse_name='fee_structure_id',
        string='Fee Lines',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_totals',
        store=True,
    )

    # ── Payment Plans ─────────────────────────────────────────────────────────────
    payment_plan_ids = fields.One2many(
        comodel_name='edu.fee.payment.plan',
        inverse_name='fee_structure_id',
        string='Payment Plans',
        help=(
            'Configurable payment plans for this fee structure. '
            'Each plan defines HOW fees are collected — installment slots or monthly billing. '
            'Students (or batches) are assigned one plan at enrollment.'
        ),
    )
    payment_plan_count = fields.Integer(
        string='Payment Plans',
        compute='_compute_totals',
        store=True,
    )

    # ── Related / convenience ─────────────────────────────────────────────────────
    company_id = fields.Many2one(
        related='program_id.company_id',
        string='Company',
        store=True,
        index=True,
    )
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
    )

    # ── SQL constraints ──────────────────────────────────────────────────────────
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Fee structure code must be unique.'),
    ]

    # ── Sequence code assignment ──────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = seq.next_by_code('edu.fee.structure') or '/'
        return super().create(vals_list)

    # ── Onchange: clear batch when scope changes ──────────────────────────────────
    @api.onchange('program_id', 'academic_year_id')
    def _onchange_scope(self):
        if self.batch_id and (
            self.batch_id.program_id != self.program_id
            or self.batch_id.academic_year_id != self.academic_year_id
        ):
            self.batch_id = False

    # ── Computed: totals ──────────────────────────────────────────────────────────
    @api.depends('line_ids.amount', 'payment_plan_ids')
    def _compute_totals(self):
        line_data = self.env['edu.fee.structure.line']._read_group(
            [('fee_structure_id', 'in', self.ids)],
            ['fee_structure_id'],
            ['__count', 'amount:sum'],
        )
        line_mapped = {s.id: (count, total) for s, count, total in line_data}

        plan_data = self.env['edu.fee.payment.plan']._read_group(
            [('fee_structure_id', 'in', self.ids)],
            ['fee_structure_id'],
            ['__count'],
        )
        plan_mapped = {s.id: count for s, count in plan_data}

        for rec in self:
            count, total = line_mapped.get(rec.id, (0, 0.0))
            rec.line_count = count
            rec.total_amount = total
            rec.payment_plan_count = plan_mapped.get(rec.id, 0)

    # ── Python constraints ────────────────────────────────────────────────────────
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
                    f'intake year "{rec.academic_year_id.name}".'
                )

    @api.constrains('program_id', 'academic_year_id', 'batch_id')
    def _check_unique_scope(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('program_id', '=', rec.program_id.id),
                ('academic_year_id', '=', rec.academic_year_id.id),
                ('batch_id', '=', rec.batch_id.id if rec.batch_id else False),
                ('active', 'in', [True, False]),
            ]
            if self.search_count(domain):
                scope = f'{rec.program_id.name} / {rec.academic_year_id.name}'
                if rec.batch_id:
                    scope += f' / {rec.batch_id.name}'
                raise ValidationError(
                    f'A fee structure for "{scope}" already exists. '
                    'Only one fee structure is allowed per program/intake year/batch scope.'
                )

    # ── Write locking ─────────────────────────────────────────────────────────────
    _UNLOCKED_FIELDS = frozenset({
        'state', 'active', 'note',
        'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })

    def write(self, vals):
        if vals.keys() - self._UNLOCKED_FIELDS:
            closed = self.filtered(lambda r: r.state == 'closed')
            if closed:
                raise UserError(
                    f'Cannot modify fee structure "{closed[0].name}" — '
                    'it is closed. Reset it to Draft first.'
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    f'Cannot delete fee structure "{rec.name}" — '
                    f'it is {rec.state}. Archive it instead.'
                )
        return super().unlink()

    # ── State transitions ─────────────────────────────────────────────────────────
    def action_activate(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(
                    f'Cannot activate fee structure "{rec.name}" — '
                    'add at least one fee line first.'
                )
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ── Smart buttons ─────────────────────────────────────────────────────────────
    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fee Lines — {self.name}',
            'res_model': 'edu.fee.structure.line',
            'view_mode': 'list,form',
            'domain': [('fee_structure_id', '=', self.id)],
            'context': {'default_fee_structure_id': self.id},
        }

    def action_view_payment_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payment Plans — {self.name}',
            'res_model': 'edu.fee.payment.plan',
            'view_mode': 'list,form',
            'domain': [('fee_structure_id', '=', self.id)],
            'context': {'default_fee_structure_id': self.id},
        }

    # ═════════════════════════════════════════════════════════════════════════════
    # Integration helpers — designed for admission, enrollment, and billing modules
    # ═════════════════════════════════════════════════════════════════════════════

    def get_fee_summary(self):
        """
        Returns the full program fee breakdown grouped by progression stage
        (program_term_id), sorted by progression_no.

        Each bucket represents one semester/trimester/stage.
        Lines within each bucket are sorted by sequence.

        Primary integration hook for:
          - Admission module: render fee schedule in offer letters
          - Enrollment module: generate student fee assignments
          - Billing module: produce per-stage invoices

        Returns:
            list[dict]:
                [
                    {
                        'program_term_id': int,
                        'program_term_name': str,
                        'progression_no': int,
                        'academic_year': str,
                        'lines': [
                            {
                                'fee_head_id': int,
                                'fee_head': str,
                                'fee_type': str,
                                'amount': float,
                                'mandatory': bool,
                                'scholarship_allowed': bool,
                                'refundable': bool,
                            },
                            ...
                        ],
                        'subtotal': float,
                        'mandatory_subtotal': float,
                        'scholarship_eligible_subtotal': float,
                    },
                    ...
                ]
        """
        self.ensure_one()
        buckets = {}
        for line in self.line_ids.sorted(key=lambda l: (l.progression_no, l.sequence)):
            pt = line.program_term_id
            if pt.id not in buckets:
                buckets[pt.id] = {
                    'program_term_id': pt.id,
                    'program_term_name': pt.display_name,
                    'progression_no': pt.progression_no,
                    'academic_year': self.academic_year_id.name,
                    'lines': [],
                    'subtotal': 0.0,
                    'mandatory_subtotal': 0.0,
                    'scholarship_eligible_subtotal': 0.0,
                }
            buckets[pt.id]['lines'].append({
                'fee_head_id': line.fee_head_id.id,
                'fee_head': line.fee_head_id.name,
                'fee_type': line.fee_head_id.fee_type,
                'payment_trigger': line.payment_trigger or None,
                'amount': line.amount,
                'mandatory': line.mandatory,
                'scholarship_allowed': line.scholarship_allowed,
                'refundable': line.refundable,
            })
            buckets[pt.id]['subtotal'] += line.amount
            if line.mandatory:
                buckets[pt.id]['mandatory_subtotal'] += line.amount
            if line.scholarship_allowed:
                buckets[pt.id]['scholarship_eligible_subtotal'] += line.amount
        return sorted(buckets.values(), key=lambda b: b['progression_no'])

    def get_payment_plans(self):
        """
        Returns all payment plans for this fee structure with full detail.

        Designed for:
          - Enrollment module: present plan choices to student
          - Billing module: generate invoices per the assigned plan

        Returns:
            list[dict]:
                [
                    {
                        'plan_id': int,
                        'name': str,
                        'plan_type': 'installment' | 'monthly',
                        # For monthly plans:
                        'months_count': int,
                        'excluded_fee_heads': [{'id': int, 'name': str}, ...],
                        # For installment plans:
                        'installments': [
                            {
                                'sequence': int,
                                'label': str,
                                'fee_heads': [{'id': int, 'name': str}, ...],
                            },
                            ...
                        ],
                    },
                    ...
                ]
        """
        self.ensure_one()
        result = []
        for plan in self.payment_plan_ids.sorted('sequence'):
            plan_dict = {
                'plan_id': plan.id,
                'name': plan.name,
                'plan_type': plan.plan_type,
                'months_count': plan.months_count,
                'excluded_fee_heads': [
                    {'id': fh.id, 'name': fh.name}
                    for fh in plan.excluded_fee_head_ids
                ],
                'installments': [
                    {
                        'sequence': line.sequence,
                        'label': line.label,
                        'fee_heads': [
                            {'id': fh.id, 'name': fh.name}
                            for fh in line.fee_head_ids
                        ],
                    }
                    for line in plan.installment_line_ids.sorted('sequence')
                ],
            }
            result.append(plan_dict)
        return result

    def get_scholarship_applicable_total(self):
        """
        Returns the total amount of fee lines eligible for scholarship/discount.

        Used by:
          - Admission module: scholarship proposal calculations
          - Offer letter: display maximum possible discount
        """
        self.ensure_one()
        return sum(
            self.line_ids.filtered(lambda l: l.scholarship_allowed).mapped('amount')
        )
