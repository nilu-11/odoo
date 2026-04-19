from odoo import api, fields, models


class EduInteractionLog(models.Model):
    _name = 'edu.interaction.log'
    _description = 'Interaction Log'
    _order = 'date desc, id desc'
    _rec_name = 'summary'

    lead_id = fields.Many2one(
        comodel_name='crm.lead',
        string='Lead',
        required=True,
        ondelete='cascade',
        index=True,
    )
    applicant_profile_id = fields.Many2one(
        related='lead_id.applicant_profile_id',
        string='Applicant',
        store=True,
        index=True,
    )
    interaction_type = fields.Selection(
        selection=[
            ('call', 'Call'),
            ('campus_visit', 'Campus Visit'),
            ('counseling_session', 'Counseling Session'),
            ('parent_meeting', 'Parent Meeting'),
            ('email', 'Email'),
            ('walk_in', 'Walk-in'),
            ('video_call', 'Video Call'),
            ('other', 'Other'),
        ],
        string='Type',
        required=True,
        default='call',
        index=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    duration_minutes = fields.Integer(string='Duration (min)')
    counselor_id = fields.Many2one(
        comodel_name='res.users',
        string='Counselor',
        default=lambda self: self.env.user,
        index=True,
    )
    outcome = fields.Selection(
        selection=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
        ],
        string='Outcome',
    )
    summary = fields.Char(string='Summary')
    note = fields.Text(string='Notes')
    activity_id = fields.Many2one(
        comodel_name='mail.activity',
        string='Source Activity',
        ondelete='set null',
        index=True,
    )
    company_id = fields.Many2one(
        related='lead_id.company_id',
        store=True,
        index=True,
    )
