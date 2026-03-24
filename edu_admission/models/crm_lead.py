from odoo import api, models


class CrmLead(models.Model):
    """
    Extend CRM lead conversion to populate full admission context
    when creating applications from the edu_admission module.
    """

    _inherit = 'crm.lead'

    def _prepare_admission_application_vals(self, register=None):
        """
        Extend base vals with admission-specific fields when
        the edu_admission module is installed.
        """
        vals = super()._prepare_admission_application_vals(register=register)
        if register:
            # Populate fee context from register
            if register.fee_structure_id:
                vals['fee_structure_id'] = register.fee_structure_id.id
            if register.available_payment_plan_ids:
                vals['available_payment_plan_ids'] = [
                    (6, 0, register.available_payment_plan_ids.ids)
                ]
            if register.default_payment_plan_id:
                vals['selected_payment_plan_id'] = (
                    register.default_payment_plan_id.id
                )
        return vals
