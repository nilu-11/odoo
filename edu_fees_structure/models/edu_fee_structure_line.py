from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EduFeeStructureLine(models.Model):
    _name = 'edu.fee.structure.line'
    _description = 'Fee Structure Line — fee amount per program progression stage'
    _order = 'fee_structure_id, progression_no, sequence, id'
    _rec_name = 'fee_head_id'

    # ── Core FKs ─────────────────────────────────────────────────────────────────
    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        required=True,
        ondelete='cascade',
        index=True,
    )
    program_term_id = fields.Many2one(
        comodel_name='edu.program.term',
        string='Progression Stage',
        required=True,
        ondelete='restrict',
        index=True,
        help=(
            'The program progression stage this fee applies to '
            '(e.g. BCA Semester 1). '
            'Must belong to the same program as the fee structure.'
        ),
    )
    fee_head_id = fields.Many2one(
        comodel_name='edu.fee.head',
        string='Fee Head',
        required=True,
        ondelete='restrict',
        index=True,
    )

    # ── Billing trigger (optional) ────────────────────────────────────────────────
    payment_trigger = fields.Selection(
        selection=[
            ('at_admission', 'At Admission'),
            ('at_exam_registration', 'At Exam Registration'),
            ('before_exam', 'Before Exam'),
            ('before_result', 'Before Result'),
            ('custom', 'Custom'),
        ],
        string='Billing Trigger',
        help=(
            'When this fee is billed — used for standalone fees that fall outside '
            'the installment/monthly plan (e.g. Admission Fee, University Reg Fee). '
            'Leave blank for fees handled by the payment plan.'
        ),
    )

    # ── Amount ───────────────────────────────────────────────────────────────────
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
        default=0.0,
        help='Total amount for this fee (full amount for the stage).',
    )

    # ── Control flags ─────────────────────────────────────────────────────────────
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Required fee that cannot be waived.',
    )
    scholarship_allowed = fields.Boolean(
        string='Scholarship Eligible',
        default=False,
        help='A scholarship or discount may be applied to this fee line.',
    )
    refundable = fields.Boolean(
        string='Refundable',
        default=False,
        help='Defaults from the fee head. Overrideable per line.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    note = fields.Text(string='Note')

    # ── Stored related fields ─────────────────────────────────────────────────────
    progression_no = fields.Integer(
        related='program_term_id.progression_no',
        string='Progression No.',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='fee_structure_id.currency_id',
        string='Currency',
        store=True,
    )
    fee_type = fields.Selection(
        related='fee_head_id.fee_type',
        string='Fee Type',
        store=True,
        index=True,
    )
    program_id = fields.Many2one(
        related='fee_structure_id.program_id',
        string='Program',
        store=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        related='fee_structure_id.academic_year_id',
        string='Intake Year',
        store=True,
        index=True,
    )
    batch_id = fields.Many2one(
        related='fee_structure_id.batch_id',
        string='Batch',
        store=True,
    )
    company_id = fields.Many2one(
        related='fee_structure_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ── SQL constraint ────────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'unique_line',
            'UNIQUE(fee_structure_id, program_term_id, fee_head_id)',
            'A fee head can only appear once per progression stage in a fee structure.',
        ),
    ]

    # ── Python constraints ────────────────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(
                    f'Amount cannot be negative — '
                    f'"{rec.fee_head_id.name}" on '
                    f'"{rec.program_term_id.display_name}".'
                )

    @api.constrains('program_term_id', 'fee_structure_id')
    def _check_program_term_scope(self):
        """program_term must belong to the same program as the fee structure."""
        for rec in self:
            if rec.program_term_id.program_id != rec.fee_structure_id.program_id:
                raise ValidationError(
                    f'Progression stage "{rec.program_term_id.display_name}" '
                    f'does not belong to program '
                    f'"{rec.fee_structure_id.program_id.name}".'
                )

    # ── Onchange ──────────────────────────────────────────────────────────────────
    @api.onchange('fee_head_id')
    def _onchange_fee_head_id(self):
        if self.fee_head_id:
            self.refundable = self.fee_head_id.is_refundable

    # ── Write / unlink locking ─────────────────────────────────────────────────────
    _CHATTER_FIELDS = frozenset({
        'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })
    _ACTIVE_STRUCT_UNLOCKED = frozenset({
        'amount', 'mandatory', 'scholarship_allowed', 'refundable',
        'sequence', 'note', 'payment_trigger',
        'message_follower_ids', 'message_ids',
        'activity_ids', 'activity_state', 'activity_date_deadline',
        'activity_summary', 'activity_type_id', 'activity_user_id',
    })

    def write(self, vals):
        writing_keys = set(vals.keys())
        for rec in self:
            state = rec.fee_structure_id.state
            if state == 'closed' and writing_keys - self._CHATTER_FIELDS:
                raise UserError(
                    f'Cannot modify fee line — fee structure '
                    f'"{rec.fee_structure_id.name}" is closed.'
                )
            if state == 'active' and writing_keys - self._ACTIVE_STRUCT_UNLOCKED:
                raise UserError(
                    f'Cannot change the progression stage or fee head on an active fee structure '
                    f'"{rec.fee_structure_id.name}". Reset it to Draft first.'
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.fee_structure_id.state != 'draft':
                raise UserError(
                    f'Cannot delete fee line from '
                    f'"{rec.fee_structure_id.name}" — '
                    f'structure is {rec.fee_structure_id.state}. '
                    'Reset it to Draft first.'
                )
        return super().unlink()
