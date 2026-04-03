from odoo import api, fields, models


class HospitalAppointment(models.Model):
	_name = "hospital.appointment"
	_inherit = ["mail.thread"]
	_description = "Hospital Appointment"
	_rec_name="patient_id"

	reference = fields.Char(
		string="Reference",
		required=True,
		readonly=True,
		default="New",
		tracking=True,
	)
	patient_id = fields.Many2one(
		"hospital.patient",
		string="Patient",
		required=True,
		tracking=True,
	)
	date_appointment = fields.Date(string="Appointment Date", tracking=True)
	note = fields.Text(string="Notes")
	state = fields.Selection(
		[
			("draft", "Draft"),
			("confirmed", "Confirmed"),
			("cancel", "Cancelled"),
			("done", "Done"),
		],
		string="Status",
		default="draft",
		tracking=True,
	)

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if vals.get("reference", "New") == "New":
				vals["reference"] = self.env["ir.sequence"].next_by_code("hospital.appointment") or "New"
		return super().create(vals_list)

	def action_confirm(self):
		for rec in self:
			rec.state='confirmed'
		
	def action_ongoing(self):
		for rec in self:
			rec.state='ongoing'

	def action_done(self):
		for rec in self:
			rec.state='done'

	def action_cancel(self):
		for rec in self:
			rec.state='cancel'
