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