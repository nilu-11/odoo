from odoo import _, api, fields, models
from odoo.exceptions import UserError


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

    def action_convert_to_admission_application(self):
        """
        Override base conversion with smart register selection.

        - If exactly one open register matches the program → convert directly
        - If zero or multiple → open wizard for user to select batch/register
        """
        self.ensure_one()
        self._check_conversion_readiness()

        Application = self.env['edu.admission.application']
        Register = self.env['edu.admission.register']

        # Guard: prevent re-conversion on same lead
        existing = Application.search(
            [('crm_lead_id', '=', self.id)], limit=1
        )
        if existing:
            raise UserError(
                _('An admission application already exists for this lead '
                  '("%(app)s"). Cannot create a duplicate.',
                  app=existing.display_name)
            )

        # Guard: no active application for same applicant + program
        duplicate_app = Application.search([
            ('applicant_profile_id', '=', self.applicant_profile_id.id),
            ('program_id', '=', self.interested_program_id.id),
            ('state', 'not in', ['rejected', 'withdrawn']),
        ], limit=1)
        if duplicate_app:
            raise UserError(
                _('Applicant "%(name)s" already has an active application for '
                  '"%(prog)s" (%(app)s). Duplicate applications are not allowed.',
                  name=self.applicant_profile_id.full_name,
                  prog=self.interested_program_id.name,
                  app=duplicate_app.display_name)
            )

        # Find all matching open registers
        register_domain = [
            ('program_id', '=', self.interested_program_id.id),
            ('state', '=', 'open'),
        ]
        if self.intended_academic_year_id:
            register_domain.append(
                ('academic_year_id', '=', self.intended_academic_year_id.id)
            )
        registers = Register.search(register_domain)

        # Exactly one register → convert directly
        if len(registers) == 1:
            register = registers
            vals = self._prepare_admission_application_vals(register=register)
            if register.batch_id:
                vals['batch_id'] = register.batch_id.id
            application = Application.create(vals)
            self.write({
                'is_converted_to_application': True,
                'conversion_date': fields.Datetime.now(),
                'lead_education_status': 'converted',
            })
            return {
                'type': 'ir.actions.act_window',
                'name': _('Admission Application'),
                'res_model': 'edu.admission.application',
                'res_id': application.id,
                'view_mode': 'form',
                'target': 'current',
            }

        # Zero or multiple → open wizard for selection
        wizard_vals = {
            'lead_id': self.id,
            'program_id': self.interested_program_id.id,
            'academic_year_id': (
                self.intended_academic_year_id.id
                if self.intended_academic_year_id else False
            ),
        }
        if self.preferred_batch_id:
            wizard_vals['batch_id'] = self.preferred_batch_id.id
            matching = registers.filtered(
                lambda r: r.batch_id == self.preferred_batch_id
            )
            if matching:
                wizard_vals['admission_register_id'] = matching[0].id

        wizard = self.env['edu.convert.to.application.wizard'].create(
            wizard_vals
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Convert to Application'),
            'res_model': 'edu.convert.to.application.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
