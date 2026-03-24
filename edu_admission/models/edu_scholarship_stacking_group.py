from odoo import fields, models


class EduScholarshipStackingGroup(models.Model):
    """
    Optional master model to classify scholarship stacking logic.

    Schemes in the same stacking group may have restrictions on combining.
    Examples: merit, financial_need, sibling, promotional, partner_discount.
    """

    _name = 'edu.scholarship.stacking.group'
    _description = 'Scholarship Stacking Group'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Group Name', required=True, translate=True)
    code = fields.Char(
        string='Code',
        help='Short identifier, e.g. MERIT, NEED, SIBLING.',
    )
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            'code_company_unique',
            'UNIQUE(code, company_id)',
            'Stacking group code must be unique per company.',
        ),
    ]
