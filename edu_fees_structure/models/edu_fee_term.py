from odoo import api, fields, models
from odoo.exceptions import UserError


class EduFeeTerm(models.Model):
    _name = 'edu.fee.term'
    _description = 'Fee Payment Term / Installment Schedule'
    _order = 'sequence, name'
    _rec_name = 'name'

    # ── Identity ────────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Fee Term',
        required=True,
        tracking=True,
        help='E.g. At Admission, Installment 1, Semester 1 Fee',
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help='Unique short code, e.g. ADM, INST1, SEM1',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Controls the display order. Lower values appear first.',
    )
    term_type = fields.Selection(
        selection=[
            ('admission', 'At Admission'),
            ('installment', 'Installment'),
            ('semester', 'Semester'),
            ('annual', 'Annual'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('trigger_based', 'Trigger-Based'),
            ('custom', 'Custom'),
        ],
        string='Term Type',
        required=True,
        default='installment',
        tracking=True,
        index=True,
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
            'Fee term code must be unique per company.',
        ),
    ]

    # ── Delete guard ─────────────────────────────────────────────────────────────
    def unlink(self):
        linked = self.env['edu.fee.structure.line'].search(
            [('fee_term_id', 'in', self.ids)], limit=1
        )
        if linked:
            raise UserError(
                'Cannot delete fee term — it is referenced by one or more fee '
                'structure lines. Archive it instead.'
            )
        return super().unlink()
