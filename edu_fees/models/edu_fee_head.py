from odoo import fields, models


class EduFeeHead(models.Model):
    """
    Extend edu.fee.head with billing-behaviour fields needed by the
    student finance module.

    New fields:
      - fee_nature        — behavioural classification (normal / deposit /
                            fine / optional) independent of the existing
                            fee_type (tuition, lab, exam …).
      - is_required_for_enrollment — when True, all dues linked to this
                            head must be paid (or overridden) before
                            enrollment can be confirmed.
      - allow_adjustment  — Stage-2 placeholder; signals that manual
                            adjustments (waivers, write-offs) are
                            permitted on dues carrying this head.
    """

    _inherit = 'edu.fee.head'

    fee_nature = fields.Selection(
        selection=[
            ('normal', 'Normal'),
            ('deposit', 'Deposit'),
            ('fine', 'Fine'),
            ('optional', 'Optional'),
        ],
        string='Fee Nature',
        default='normal',
        required=True,
        tracking=True,
        help=(
            'Behavioural classification of this fee head:\n'
            '• Normal — standard recurring or one-time charge.\n'
            '• Deposit — refundable deposit (e.g. security deposit, '
            'library deposit). Tracked separately for future refund '
            'workflows.\n'
            '• Fine — penalty charge (e.g. late fee).\n'
            '• Optional — fee that the student may opt out of.'
        ),
    )
    is_required_for_enrollment = fields.Boolean(
        string='Required for Enrollment',
        default=False,
        tracking=True,
        help=(
            'If enabled, dues linked to this fee head must be fully paid '
            '(or a manager override must be recorded) before the '
            'enrollment can be confirmed. Typical examples: admission fee, '
            'mandatory security deposit.'
        ),
    )
    allow_adjustment = fields.Boolean(
        string='Allow Adjustment',
        default=False,
        tracking=True,
        help=(
            'Stage-2 placeholder. When enabled, manual adjustments '
            '(waivers, write-offs, corrections) may be posted against '
            'dues carrying this fee head.'
        ),
    )
