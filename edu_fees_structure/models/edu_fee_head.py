from odoo import api, fields, models
from odoo.exceptions import UserError


class EduFeeHead(models.Model):
    _name = 'edu.fee.head'
    _description = 'Fee Head / Component'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fee_type, name'
    _rec_name = 'name'

    # ── Identity ────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Fee Head',
        required=True,
        tracking=True,
        help='E.g. Tuition Fee, Lab Fee, Admission Fee',
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Unique short code, e.g. TUITION, LAB, ADM',
    )
    fee_type = fields.Selection(
        selection=[
            ('admission', 'Admission'),
            ('tuition', 'Tuition'),
            ('exam', 'Exam'),
            ('library', 'Library'),
            ('lab', 'Lab'),
            ('registration', 'Registration'),
            ('university_registration', 'University Registration'),
            ('hostel', 'Hostel'),
            ('transport', 'Transport'),
            ('deposit', 'Security Deposit'),
            ('other', 'Other'),
        ],
        string='Fee Type',
        required=True,
        default='tuition',
        tracking=True,
        index=True,
    )
    is_one_time = fields.Boolean(
        string='One-Time Fee',
        default=False,
        tracking=True,
        help=(
            'If enabled, this fee is charged only once per student '
            '(e.g. admission fee, security deposit). '
            'The billing module can use this flag to avoid duplicate charges.'
        ),
    )
    is_refundable = fields.Boolean(
        string='Refundable',
        default=False,
        tracking=True,
        help=(
            'Indicates that this fee is refundable in nature. '
            'Used as the default when this head is assigned to a structure line.'
        ),
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ── SQL constraints ──────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Fee head code must be unique per company.',
        ),
    ]

    # ── Delete guard ─────────────────────────────────────────────────────────────
    def unlink(self):
        linked = self.env['edu.fee.structure.line'].search(
            [('fee_head_id', 'in', self.ids)], limit=1
        )
        if linked:
            raise UserError(
                'Cannot delete fee head — it is referenced by one or more fee '
                'structure lines. Archive it instead.'
            )
        return super().unlink()
