from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduLeadMergeWizard(models.TransientModel):
    _name = 'edu.lead.merge.wizard'
    _description = 'Merge Duplicate Leads'

    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade',
                               string='Current Lead')
    duplicate_lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade',
                                         string='Duplicate Lead')

    # Display fields for comparison
    lead_phone = fields.Char(related='lead_id.phone', readonly=True)
    lead_email = fields.Char(related='lead_id.email_from', readonly=True)
    lead_program = fields.Char(related='lead_id.interested_program_id.name', readonly=True)
    dup_phone = fields.Char(related='duplicate_lead_id.phone', readonly=True)
    dup_email = fields.Char(related='duplicate_lead_id.email_from', readonly=True)
    dup_program = fields.Char(related='duplicate_lead_id.interested_program_id.name', readonly=True)

    keep_phone_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        string='Keep Phone From', default='lead', required=True,
    )
    keep_email_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        string='Keep Email From', default='lead', required=True,
    )
    keep_program_from = fields.Selection(
        [('lead', 'Current Lead'), ('duplicate', 'Duplicate Lead')],
        string='Keep Program From', default='lead', required=True,
    )

    def action_merge(self):
        self.ensure_one()
        if self.lead_id == self.duplicate_lead_id:
            raise UserError(_("Cannot merge a lead with itself."))

        target = self.lead_id
        source = self.duplicate_lead_id

        vals = {}
        if self.keep_phone_from == 'duplicate' and source.phone:
            vals['phone'] = source.phone
        if self.keep_email_from == 'duplicate' and source.email_from:
            vals['email_from'] = source.email_from
        if self.keep_program_from == 'duplicate' and source.interested_program_id:
            vals['interested_program_id'] = source.interested_program_id.id

        if vals:
            target.write(vals)

        # Move messages from source to target
        source.message_ids.write({'res_id': target.id})

        # Archive source
        source.write({'active': False, 'lead_education_status': 'lost'})

        target.message_post(body=_(
            "Merged with duplicate lead <b>%s</b>.",
            source.display_name,
        ))

        return {'type': 'ir.actions.act_window_close'}
