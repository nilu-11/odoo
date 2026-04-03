from odoo import fields, models


class EduTeamMember(models.Model):
    """
    Pre-Admission team member (counselors, admissions officers, etc.).
    Used as the source for the Counselor field on CRM leads.
    """

    _name = 'edu.team.member'
    _description = 'Pre-Admission Team Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    # ═══ Identity / Core Fields ═══
    name = fields.Char(string='Name', required=True, tracking=True)
    job_title = fields.Char(string='Job Title', tracking=True)
    phone = fields.Char(string='Phone', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)


    image_128 = fields.Image(string='Photo', max_width=128, max_height=128)
