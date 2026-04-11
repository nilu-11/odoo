from odoo import api, fields, models

class EduQualification(models.Model):
    _name = 'edu.qualification'
    _description = 'Qualification Master'
    _order = 'sequence, name'

    name = fields.Char('Qualification Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Qualification name must be unique!'),
    ]
