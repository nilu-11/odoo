from odoo import fields, models


class EduRelationshipType(models.Model):
    _name = 'edu.relationship.type'
    _description = 'ApplicantGuardian Relationship Type'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Relationship',
        required=True,
        translate=True,
        help='E.g. Father, Mother, Legal Guardian, Sponsor.',
    )
    code = fields.Char(
        string='Code',
        help='Short identifier, e.g. FATHER, MOTHER, GUARDIAN.',
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
            'Relationship type code must be unique per company.',
        ),
    ]
