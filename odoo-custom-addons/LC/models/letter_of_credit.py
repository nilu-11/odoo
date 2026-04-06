from odoo import _, Command, api, fields, models
from odoo.exceptions import ValidationError


class LetterOfCreditType(models.Model):
    _name = "letter.of.credit.type"
    _description = "Letter of Credit Type"

    name = fields.Char(string="Type Name", required=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description")
    active = fields.Boolean(default=True)
    required_document_ids = fields.One2many(
        "letter.of.credit.type.document", "type_id", string="Required Documents"
    )

    _sql_constraints = [
        ("letter_of_credit_type_code_unique", "unique(code)", "Type code must be unique."),
    ]


class LetterOfCreditTypeDocument(models.Model):
    _name = "letter.of.credit.type.document"
    _description = "Letter of Credit Type Required Document"

    type_id = fields.Many2one("letter.of.credit.type", required=True, ondelete="cascade")
    name = fields.Char(string="Document Name", required=True)
    mandatory = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)


class LetterOfCreditDocument(models.Model):
    _name = "letter.of.credit.document"
    _description = "Letter of Credit Document"

    lc_id = fields.Many2one("letter.of.credit", string="Letter of Credit", required=True, ondelete="cascade")
    name = fields.Char(string="Document", required=True)
    mandatory = fields.Boolean(default=True)
    received_date = fields.Date(string="Received Date")
    file = fields.Binary(string="Attachment", attachment=True)
    file_name = fields.Char(string="File Name")
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("received", "Received"),
            ("accepted", "Accepted"),
            ("discrepant", "Discrepant"),
        ],
        default="pending",
        string="Status",
    )
    note = fields.Text(string="Notes")


class LetterOfCredit(models.Model):
    _name = "letter.of.credit"
    _description = "Letter of Credit"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="LC Number", default="New", readonly=True, copy=False)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    type_id = fields.Many2one("letter.of.credit.type", string="LC Type", tracking=True)
    reference = fields.Char(string="Customer Reference")
    applicant_id = fields.Many2one("res.partner", string="Applicant", required=True, tracking=True)
    beneficiary_id = fields.Many2one("res.partner", string="Beneficiary", required=True, tracking=True)
    bank_id = fields.Many2one("res.partner", string="Issuing Bank", required=True)
    advising_bank_id = fields.Many2one("res.partner", string="Advising Bank")
    confirming_bank_id = fields.Many2one("res.partner", string="Confirming Bank")
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms")
    incoterm_id = fields.Many2one("account.incoterms", string="Incoterm")
    port_of_loading = fields.Char(string="Port of Loading")
    port_of_discharge = fields.Char(string="Port of Discharge")
    latest_shipment_date = fields.Date(string="Latest Shipment Date")
    amount = fields.Float(string="Amount", required=True, tracking=True)
    issue_date = fields.Date(string="Issue Date", tracking=True)
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    notes = fields.Text(string="Terms and Conditions")
    document_ids = fields.One2many("letter.of.credit.document", "lc_id", string="Documents")
    mandatory_document_count = fields.Integer(compute="_compute_document_stats", string="Mandatory Docs")
    received_document_count = fields.Integer(compute="_compute_document_stats", string="Received Docs")
    is_expired = fields.Boolean(compute="_compute_is_expired", store=True, string="Expired")
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
        tracking=True,
    )

    _sql_constraints = [
        ("letter_of_credit_name_unique", "unique(name)", "LC Number must be unique."),
    ]

    @api.depends("document_ids.mandatory", "document_ids.status")
    def _compute_document_stats(self):
        for record in self:
            mandatory_docs = record.document_ids.filtered(lambda doc: doc.mandatory)
            received_docs = mandatory_docs.filtered(lambda doc: doc.status in ("received", "accepted"))
            record.mandatory_document_count = len(mandatory_docs)
            record.received_document_count = len(received_docs)

    @api.depends("expiry_date")
    def _compute_is_expired(self):
        today = fields.Date.today()
        for record in self:
            record.is_expired = bool(record.expiry_date and record.expiry_date < today)

    @api.onchange("type_id")
    def _onchange_type_id(self):
        if self.type_id and not self.document_ids:
            self.document_ids = self._prepare_document_lines(self.type_id)

    def _prepare_document_lines(self, lc_type):
        return [
            Command.create(
                {
                    "name": template.name,
                    "mandatory": template.mandatory,
                }
            )
            for template in lc_type.required_document_ids.sorted("sequence")
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("letter.of.credit") or "New"
            if vals.get("type_id") and not vals.get("document_ids"):
                lc_type = self.env["letter.of.credit.type"].browse(vals["type_id"])
                vals["document_ids"] = self._prepare_document_lines(lc_type)
        return super().create(vals_list)

    def action_issue(self):
        for record in self:
            if record.state != "draft":
                raise ValidationError(_("Only draft records can be issued."))
            record.state = "issued"

    def action_approve(self):
        for record in self:
            if record.state != "issued":
                raise ValidationError(_("Only issued records can be approved."))
            mandatory_docs = record.document_ids.filtered(lambda doc: doc.mandatory)
            pending_docs = mandatory_docs.filtered(
                lambda doc: doc.status not in ("received", "accepted")
            )
            if pending_docs:
                raise ValidationError(_("All mandatory documents must be received before approval."))
            record.state = "approved"

    def action_close(self):
        for record in self:
            if record.state != "approved":
                raise ValidationError(_("Only approved records can be closed."))
            record.state = "closed"

    def action_cancel(self):
        for record in self:
            if record.state == "closed":
                raise ValidationError(_("Closed records cannot be cancelled."))
            record.state = "cancelled"

    @api.constrains("amount")
    def _check_amount(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Amount must be greater than 0."))

    @api.constrains("applicant_id", "beneficiary_id")
    def _check_parties(self):
        for record in self:
            if record.applicant_id and record.beneficiary_id and record.applicant_id == record.beneficiary_id:
                raise ValidationError(_("Applicant and Beneficiary must be different partners."))

    @api.constrains("issue_date", "expiry_date")
    def _check_expiry_date(self):
        for record in self:
            if record.issue_date and record.expiry_date and record.expiry_date <= record.issue_date:
                raise ValidationError(_("Expiry Date must be after Issue Date."))