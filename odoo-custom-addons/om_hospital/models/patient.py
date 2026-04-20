from odoo import api, fields, models
from odoo.exceptions import UserError


class HospitalPatient(models.Model):
    _name = "hospital.patient"
    _description = "Patient Master"
    _inherit = ["mail.thread"]
    _rec_name = "contact_id"

    contact_id = fields.Many2one("res.partner", string="Name", required=True)
    date_of_birth = fields.Date(string="Date of Birth")
    tags_id = fields.Many2many("patient.tag", string = "Patient tags")
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female")],
        string="Gender",
    )
    appointment_ids = fields.One2many( "hospital.appointment", "patient_id", string="Appointments", )

    note = fields.Text(string="Note")
    age = fields.Integer(string="Age", compute="_compute_age")

    service_product_id = fields.Many2one(
        "product.product",
        string="Service",
        domain=[("type", "=", "service")],
    )

    sale_order_id = fields.Many2one("sale.order", string="Sale Order")

    _sql_constraints = [
        ("unique_contact", "unique(contact_id)", "Patient must be unique!")
    ]

    # -----------------------
    # Compute Age
    # -----------------------
    @api.depends("date_of_birth")
    def _compute_age(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_of_birth:
                rec.age = today.year - rec.date_of_birth.year
            else:
                rec.age = 0

    # -----------------------
    # Create Sale Order
    # -----------------------
    def action_create_sale_order(self):
        self.ensure_one()
        if self.sale_order_id:
            return self.action_open_sale_order()

        if not self.contact_id or not self.service_product_id:
            raise UserError("Select contact and service first.")

        order = self.env["sale.order"].create({
            "partner_id": self.contact_id.id,
            "order_line": [(0, 0, {
                "product_id": self.service_product_id.id,
                "product_uom_qty": 1,
                "price_unit": self.service_product_id.list_price,
            })],
        })

        self.sale_order_id = order.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }

    # -----------------------
    # Open Sale Order
    # -----------------------
    def action_open_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError("No sale order found.")
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
        }