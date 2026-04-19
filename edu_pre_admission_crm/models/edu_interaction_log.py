from odoo import api, fields, models

# Mapping from activity type XML ID suffix to interaction_type
_ACTIVITY_INTERACTION_MAP = {
    'edu_pre_admission_crm.mail_activity_type_followup_call': 'call',
    'edu_pre_admission_crm.mail_activity_type_campus_visit': 'campus_visit',
    'edu_pre_admission_crm.mail_activity_type_counseling_session': 'counseling_session',
    'edu_pre_admission_crm.mail_activity_type_parent_meeting': 'parent_meeting',
    'mail.mail_activity_data_call': 'call',
}


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
        comodel_name='hr.employee',
        string='Counselor',
        default=lambda self: self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1,
        ),
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
        string='Link Activity',
        ondelete='set null',
        index=True,
        domain="[('res_model', '=', 'crm.lead'), ('res_id', '=', lead_id)]",
        help='Select an open activity to mark as done when saving this interaction.',
    )
    company_id = fields.Many2one(
        related='lead_id.company_id',
        store=True,
        index=True,
    )

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        """Pre-fill type and summary from the selected activity."""
        if not self.activity_id:
            return
        act = self.activity_id
        # Map activity type to interaction type
        type_map = {}
        for xml_id, itype in _ACTIVITY_INTERACTION_MAP.items():
            ref = self.env.ref(xml_id, raise_if_not_found=False)
            if ref:
                type_map[ref.id] = itype
        self.interaction_type = type_map.get(act.activity_type_id.id, 'other')
        if not self.summary:
            self.summary = act.summary or act.activity_type_id.name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Mark linked activities as done
        for rec in records:
            if rec.activity_id:
                rec.activity_id.with_context(
                    skip_interaction_log=True,
                ).action_feedback(feedback=rec.summary or '')
        return records
