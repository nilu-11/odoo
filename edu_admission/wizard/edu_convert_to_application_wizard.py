from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EduConvertToApplicationWizard(models.TransientModel):
    _name = 'edu.convert.to.application.wizard'
    _description = 'Convert Lead to Admission Application'

    lead_id = fields.Many2one('crm.lead', required=True, readonly=True)
    program_id = fields.Many2one(
        'edu.program', string="Program", readonly=True,
    )
    academic_year_id = fields.Many2one(
        'edu.academic.year', string="Academic Year", readonly=True,
    )

    # ── Selection fields ────────────────────────────────────────────────
    admission_register_id = fields.Many2one(
        'edu.admission.register',
        string="Admission Register",
        domain="[('id', 'in', available_register_ids)]",
    )
    batch_id = fields.Many2one(
        'edu.batch',
        string="Batch",
        domain="[('id', 'in', available_batch_ids)]",
    )

    # ── Available options (invisible helper fields) ─────────────────────
    available_register_ids = fields.Many2many(
        'edu.admission.register',
        compute='_compute_available_options',
    )
    available_batch_ids = fields.Many2many(
        'edu.batch',
        compute='_compute_available_options',
    )

    # ── Display helpers ─────────────────────────────────────────────────
    register_count = fields.Integer(compute='_compute_available_options')
    batch_count = fields.Integer(compute='_compute_available_options')
    info_message = fields.Html(compute='_compute_available_options')

    @api.depends('lead_id')
    def _compute_available_options(self):
        for wiz in self:
            lead = wiz.lead_id
            registers = self.env['edu.admission.register'].browse()
            batches = self.env['edu.batch'].browse()
            info = ''

            if lead and lead.interested_program_id:
                domain = [
                    ('program_id', '=', lead.interested_program_id.id),
                    ('state', '=', 'open'),
                ]
                if lead.intended_academic_year_id:
                    domain.append(
                        ('academic_year_id', '=', lead.intended_academic_year_id.id)
                    )
                registers = self.env['edu.admission.register'].search(domain)

                batch_domain = [
                    ('program_id', '=', lead.interested_program_id.id),
                    ('state', '=', 'active'),
                ]
                if lead.intended_academic_year_id:
                    batch_domain.append(
                        ('academic_year_id', '=', lead.intended_academic_year_id.id)
                    )
                batches = self.env['edu.batch'].search(batch_domain)

            if not registers:
                info = _(
                    '<p class="text-warning mb-0">'
                    '<i class="fa fa-exclamation-triangle me-1"></i>'
                    'No open admission register found for this program. '
                    'The application will be created without a register.</p>'
                )

            wiz.available_register_ids = registers
            wiz.available_batch_ids = batches
            wiz.register_count = len(registers)
            wiz.batch_count = len(batches)
            wiz.info_message = info

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        """When batch changes, try to narrow registers to that batch."""
        if self.batch_id and self.available_register_ids:
            matching = self.available_register_ids.filtered(
                lambda r: r.batch_id == self.batch_id
            )
            if matching:
                self.admission_register_id = matching[0]

    @api.onchange('admission_register_id')
    def _onchange_admission_register_id(self):
        """When register changes, sync batch from register if set."""
        if self.admission_register_id and self.admission_register_id.batch_id:
            self.batch_id = self.admission_register_id.batch_id

    def action_convert(self):
        """Execute the conversion using the selected register and batch."""
        self.ensure_one()
        lead = self.lead_id
        Application = self.env['edu.admission.application']

        # Sync selected batch back to the lead
        if self.batch_id and self.batch_id != lead.preferred_batch_id:
            lead.write({'preferred_batch_id': self.batch_id.id})

        lead._check_conversion_readiness()

        # Guard: prevent re-conversion
        existing = Application.search(
            [('crm_lead_id', '=', lead.id)], limit=1
        )
        if existing:
            raise UserError(
                _('An admission application already exists for this lead '
                  '("%(app)s"). Cannot create a duplicate.',
                  app=existing.display_name)
            )

        # Guard: duplicate for same applicant + program
        duplicate_app = Application.search([
            ('applicant_profile_id', '=', lead.applicant_profile_id.id),
            ('program_id', '=', lead.interested_program_id.id),
            ('state', 'not in', ['rejected', 'withdrawn']),
        ], limit=1)
        if duplicate_app:
            raise UserError(
                _('Applicant "%(name)s" already has an active application for '
                  '"%(prog)s" (%(app)s). Duplicate applications are not allowed.',
                  name=lead.applicant_profile_id.full_name,
                  prog=lead.interested_program_id.name,
                  app=duplicate_app.display_name)
            )

        register = self.admission_register_id or None
        vals = lead._prepare_admission_application_vals(register=register)
        if self.batch_id:
            vals['batch_id'] = self.batch_id.id
        application = Application.create(vals)

        lead.write({
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
