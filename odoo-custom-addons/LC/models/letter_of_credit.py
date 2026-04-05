from odoo import fields, models


class LetterOfCredit(models.Model):
    _name = "letter.of.credit"
    _description = "Letter of Credit"

    name = fields.Char(string="Name", default="New", readonly=True)
    applicant_id = fields.Many2one("res.partner", string="Applicant")
    beneficiary_id = fields.Many2one("res.partner", string="Beneficiary")
    bank_id = fields.Many2one("res.partner", string="Bank")
    amount = fields.Float(string="Amount", required=True)
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("approved", "Approved"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="draft",
    )