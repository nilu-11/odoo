from odoo import api, fields, models

class HospitalPatient(models.Model):
    _name = "hospital.patient"   #tech name of the model
    _inherit = ['mail.thread']          #chatter box renders the mail inbox    
    _description = "Patient Master"  #shown in UI

    name = fields.Char(string="Name", required=True, tracking=True)  #tracking true enables the changes made by user in the chatter box
    date_of_birth = fields.Date(string="Date of Birth", tracking=True) 
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')                                                                                                                                                                                
    ], string = "Gender", tracking=True)
    
    tags_id = fields.Many2many("patient.tag", String="Tags")
    age = fields.Integer(string="Age", compute="_compute_age")
    appointment_ids = fields.One2many(
        "hospital.appointment",
        "patient_id",
        string="Appointments",
    )

    _name_unique = models.Constraint(
        'unique(name)', 
        'The name must be unique!',
    )

    @api.depends("date_of_birth")
    def _compute_age(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_of_birth:
                rec.age = today.year - rec.date_of_birth.year
            else:
                rec.age = 0
    