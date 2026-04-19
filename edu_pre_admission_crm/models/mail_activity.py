from odoo import models

_ACTIVITY_TYPE_MAP = {
    'mail_activity_type_followup_call': 'call',
    'mail_activity_type_campus_visit': 'campus_visit',
    'mail_activity_type_counseling_session': 'counseling_session',
    'mail_activity_type_parent_meeting': 'parent_meeting',
}


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _action_done(self, feedback=False, attachment_ids=None):
        log_vals_list = []
        edu_type_ids = {}
        for xml_id_suffix, interaction_type in _ACTIVITY_TYPE_MAP.items():
            ref = self.env.ref(
                f'edu_pre_admission_crm.{xml_id_suffix}',
                raise_if_not_found=False,
            )
            if ref:
                edu_type_ids[ref.id] = interaction_type

        if edu_type_ids:
            for activity in self:
                if (
                    activity.res_model == 'crm.lead'
                    and activity.activity_type_id.id in edu_type_ids
                ):
                    log_vals_list.append({
                        'lead_id': activity.res_id,
                        'interaction_type': edu_type_ids[activity.activity_type_id.id],
                        'date': activity.date_deadline,
                        'counselor_id': self.env.uid,
                        'summary': feedback or activity.summary or activity.activity_type_id.name,
                        'activity_id': activity.id,
                    })

        result = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)

        if log_vals_list:
            self.env['edu.interaction.log'].sudo().create(log_vals_list)

        return result
