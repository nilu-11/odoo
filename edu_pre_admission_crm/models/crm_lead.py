from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class CrmLead(models.Model):
    """
    CRM Lead extension for the EMIS pre-admission workflow.

    Role of crm.lead in EMIS:
    - Pipeline engine: stages, activities, follow-ups, lost reasons
    - Counseling workspace: notes, counselor assignment, qualification
    - Conversion trigger: generates edu.admission.application when ready

    What crm.lead does NOT store:
    - Applicant personal/demographic data → edu.applicant.profile
    - Guardian data → edu.guardian + edu.applicant.guardian.rel
    - Academic history → edu.applicant.academic.history

    The lead only holds the workflow state and pointers to those structured models.
    """

    _inherit = 'crm.lead'

    # ── Education Workflow Status ──────────────────────────────────────────────
    lead_education_status = fields.Selection(
        selection=[
            ('inquiry', 'Inquiry'),
            ('prospect', 'Prospect'),
            ('qualified', 'Qualified'),
            ('ready_for_application', 'Ready for Application'),
            ('converted', 'Converted'),
            ('lost', 'Lost'),
        ],
        string='Education Status',
        default='inquiry',
        required=True,
        tracking=True,
        index=True,
        copy=False,
        group_expand='_group_expand_lead_education_status',
        help=(
            'Education workflow stage, independent of CRM pipeline stage. '
            'Tracks pre-admission progression from first contact to application.'
        ),
    )

    # ── Timeline ──────────────────────────────────────────────────────────────
    inquiry_date = fields.Date(
        string='Inquiry Date',
        default=fields.Date.today,
        tracking=True,
        help='Date the first inquiry was received.',
    )
    last_contact_date = fields.Date(
        string='Last Contact Date',
        tracking=True,
    )
    next_followup_date = fields.Date(
        string='Next Follow-up Date',
        tracking=True,
    )

    # ── Counseling ────────────────────────────────────────────────────────────
    counselor_id = fields.Many2one(
        comodel_name='res.users',
        string='Counselor',
        tracking=True,
        help='Internal user responsible for counseling this prospect.',
    )    
    referred_by_id = fields.Many2one(
        comodel_name='res.partner',
        string='Referred By',
        tracking=True,
        ondelete='restrict',
        help='Contact who referred this applicant.',
    )
    counseling_note = fields.Text(string='Counseling Notes')
    qualification_note = fields.Text(string='Qualification Notes')

    # ── Academic Interest ─────────────────────────────────────────────────────
    interested_program_id = fields.Many2one(
        comodel_name='edu.program',
        string='Enrolled Program',
        tracking=True,
        ondelete='restrict',
        index=True,
        help='The program the applicant is inquiring about.',
    )
    other_interested_program_ids = fields.Many2many(
        comodel_name='edu.program',
        string='Interested Programs',
        tracking=True,
        ondelete='restrict',
        index=True,
        help=(
            'Other programs the applicant has expressed interest in. '
            'For example, if they are interested in both BCA and BBA'
        ),
    )


    intended_academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Intended Intake Year',
        tracking=True,
        ondelete='restrict',
        help='The academic/intake year the applicant intends to join.',
    )
    preferred_batch_id = fields.Many2one(
        comodel_name='edu.batch',
        string='Preferred Batch',
        tracking=True,
        ondelete='restrict',
        domain=(
            "[('program_id', '=', interested_program_id), "
            "('academic_year_id', '=', intended_academic_year_id)]"
        ),
        help='Specific batch within the program/year (optional).',
    )
    preferred_term_id = fields.Many2one(
        comodel_name='edu.term',
        string='Preferred Term',
        tracking=True,
        ondelete='restrict',
        help='Preferred enrollment term (e.g. Semester 1 2026).',
    )
    # ── Academic Background ────────────────────────────────────────────────────
    qualification = fields.Char(
        string='Qualification',
        tracking=True,
        help='Highest qualification of the applicant, e.g. A-Levels, Bachelor of Science.',
    )
    cgpa_percentage = fields.Float(
        string='CGPA / Percentage',
        digits=(5, 2),
        tracking=True,
        help='CGPA (e.g. 3.75) or percentage (e.g. 82.50) from the last qualification.',
    )

    scholarship_interest = fields.Boolean(
        string='Scholarship Interest',
        default=False,
        tracking=True,
    )
    hostel_interest = fields.Boolean(
        string='Hostel Interest',
        default=False,
        tracking=True,
    )
    transport_interest = fields.Boolean(
        string='Transport Interest',
        default=False,
        tracking=True,
    )

    # ── Quick Profile Creation ─────────────────────────────────────────────────
    quick_applicant_name = fields.Char(
        string='Applicant Name',
        help=(
            'Type the full name (e.g. "Ram Shah") and click "Create Profile". '
            'The first word becomes the First Name; the remaining words become the Last Name.'
        ),
    )
    show_advanced_options = fields.Boolean(
        string='Advanced Options',
        default=False,
    )

    # ── Applicant Profile Link ────────────────────────────────────────────────
    applicant_profile_id = fields.Many2one(
        comodel_name='edu.applicant.profile',
        string='Applicant Profile',
        tracking=True,
        ondelete='restrict',
        index=True,
        copy=False,
        help=(
            'Structured applicant identity record. '
            'Must be set before converting to an admission application.'
        ),
    )

    # ── Conversion ────────────────────────────────────────────────────────────
    is_converted_to_application = fields.Boolean(
        string='Converted to Application',
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
    )
    conversion_date = fields.Datetime(
        string='Conversion Date',
        readonly=True,
        copy=False,
        tracking=True,
    )

    def _create_profile_from_quick_name(self):
        """Split quick_applicant_name and create a partner + applicant profile."""
        self.ensure_one()
        name = (self.quick_applicant_name or '').strip()
        if not name:
            raise UserError(
                f'Lead "{self.name}": please set an Applicant Name before marking as Qualified.'
            )
        parts = name.split()
        if len(parts) < 2:
            raise UserError(
                f'Lead "{self.name}": enter both a first and last name '
                '(e.g. "Ram Shah") in the Applicant Name field.'
            )
        first_name = parts[0]
        last_name = ' '.join(parts[1:])
        partner = self.env['res.partner'].create({
            'name': name,
            'email': self.email_from or False,
            'phone': self.phone or False,
        })
        profile = self.env['edu.applicant.profile'].create({
            'first_name': first_name,
            'last_name': last_name,
            'partner_id': partner.id,
        })
        self.write({
            'applicant_profile_id': profile.id,
            'partner_id': partner.id,
            'quick_applicant_name': False,
        })

    # ── Onchange: clear batch when program/year changes ───────────────────────
    @api.onchange('interested_program_id', 'intended_academic_year_id')
    def _onchange_academic_interest_scope(self):
        if self.preferred_batch_id and (
            self.preferred_batch_id.program_id != self.interested_program_id
            or self.preferred_batch_id.academic_year_id != self.intended_academic_year_id
        ):
            self.preferred_batch_id = False

    @api.onchange('applicant_profile_id')
    def _onchange_applicant_profile_id_set_partner(self):
        if self.applicant_profile_id and self.applicant_profile_id.partner_id:
            self.partner_id = self.applicant_profile_id.partner_id

    # ── Computed: call-only activity lists ─────────────────────────────────────
    pending_call_activity_ids = fields.One2many(
        comodel_name='mail.activity',
        compute='_compute_call_activities',
        string='Pending Call Activities',
    )
    done_call_message_ids = fields.One2many(
        comodel_name='mail.message',
        compute='_compute_call_activities',
        string='Done Call Activities',
    )

    def _compute_call_activities(self):
        call_type = self.env.ref('mail.mail_activity_data_call', raise_if_not_found=False)
        for rec in self:
            if call_type:
                rec.pending_call_activity_ids = rec.activity_ids.filtered(
                    lambda a: a.activity_type_id == call_type
                )
                rec.done_call_message_ids = rec.message_ids.filtered(
                    lambda m: m.mail_activity_type_id == call_type
                )
            else:
                rec.pending_call_activity_ids = self.env['mail.activity']
                rec.done_call_message_ids = self.env['mail.message']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            applicant_id = vals.get('applicant_profile_id')
            if applicant_id:
                applicant = self.env['edu.applicant.profile'].browse(applicant_id)
                if applicant.exists() and applicant.partner_id:
                    vals['partner_id'] = applicant.partner_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('applicant_profile_id'):
            applicant = self.env['edu.applicant.profile'].browse(
                vals['applicant_profile_id']
            )
            if applicant.exists() and applicant.partner_id:
                vals = dict(vals, partner_id=applicant.partner_id.id)
        return super().write(vals)

    # ═════════════════════════════════════════════════════════════════════════    # Group Expand — always show all status columns in kanban
    # ═══════════════════════════════════════════════════════════════════════════

    @api.model
    def _group_expand_lead_education_status(self, statuses, domain):
        """Return all selection values so kanban always shows every column."""
        return [key for key, _label in self._fields['lead_education_status'].selection]

    # ═══════════════════════════════════════════════════════════════════════════    # Education Status Transitions
    # ═════════════════════════════════════════════════════════════════════════

    def action_set_prospect(self):
        self.filtered(
            lambda r: r.lead_education_status == 'inquiry'
        ).write({'lead_education_status': 'prospect'})

    def action_set_qualified(self):
        for rec in self.filtered(
            lambda r: r.lead_education_status in ('inquiry', 'prospect')
        ):
            if not rec.applicant_profile_id:
                rec._create_profile_from_quick_name()
            rec.write({'lead_education_status': 'qualified'})

    def action_set_ready_for_application(self):
        for rec in self:
            if not rec.applicant_profile_id:
                raise UserError(
                    f'Lead "{rec.name}" cannot be marked Ready for Application — '
                    'link an Applicant Profile first.'
                )
            if not rec.interested_program_id:
                raise UserError(
                    f'Lead "{rec.name}" cannot be marked Ready for Application — '
                    'set the Interested Program first.'
                )
        self.write({'lead_education_status': 'ready_for_application'})

    # ═════════════════════════════════════════════════════════════════════════
    # Conversion to Admission Application
    # ═════════════════════════════════════════════════════════════════════════

    def _check_conversion_readiness(self):
        """Raise UserError with all blocking issues collected in one message."""
        self.ensure_one()
        errors = []
        if not self.partner_id:
            errors.append('Contact (partner) is not set on the lead.')
        if not self.applicant_profile_id:
            errors.append('Applicant Profile is not linked.')
        if not self.interested_program_id:
            errors.append('Interested Program is not set.')
        if self.is_converted_to_application:
            errors.append(
                'This lead has already been converted to an admission application.'
            )
        if errors:
            raise UserError(
                'Cannot convert — please resolve the following:\n'
                + '\n'.join(f'  • {e}' for e in errors)
            )

    def _suggest_admission_register(self):
        """
        Attempts to find an open admission register for this lead's program/year.
        Returns the register record or None.
        Requires edu_admission to be installed.
        """
        self.ensure_one()
        register_model = self.env.get('edu.admission.register')
        if not register_model:
            return None
        domain = [
            ('program_id', '=', self.interested_program_id.id),
            ('state', '=', 'open'),
        ]
        if self.intended_academic_year_id:
            domain.append(
                ('academic_year_id', '=', self.intended_academic_year_id.id)
            )
        return register_model.search(domain, limit=1) or None

    def _prepare_admission_application_vals(self, register=None):
        """
        Returns the vals dict for creating edu.admission.application.
        The admission module may extend this via super() in its own crm.lead inherit.
        """
        self.ensure_one()
        vals = {
            'partner_id': self.partner_id.id,
            'applicant_profile_id': self.applicant_profile_id.id,
            'program_id': self.interested_program_id.id,
            'crm_lead_id': self.id,
        }
        if self.intended_academic_year_id:
            vals['academic_year_id'] = self.intended_academic_year_id.id
        if self.preferred_batch_id:
            vals['batch_id'] = self.preferred_batch_id.id
        if register:
            vals['admission_register_id'] = register.id
        return vals

    def action_convert_to_admission_application(self):
        """
        Converts this CRM lead into a formal edu.admission.application.

        Requires:
          - applicant_profile_id set
          - partner_id set
          - interested_program_id set
          - edu_admission module installed

        On success:
          - Creates edu.admission.application
          - Marks lead as converted
          - Returns an action to open the new application
        """
        self.ensure_one()
        self._check_conversion_readiness()

        application_model = self.env.get('edu.admission.application')
        if application_model is None:
            raise UserError(
                'The edu_admission module is not installed.\n'
                'Install it to enable conversion to admission applications.'
            )

        # Guard: prevent re-conversion on same lead
        existing = application_model.search(
            [('crm_lead_id', '=', self.id)], limit=1
        )
        if existing:
            raise UserError(
                f'An admission application already exists for this lead '
                f'("{existing.display_name}"). Cannot create a duplicate.'
            )

        # Guard: no active application for same applicant profile on same program
        duplicate_app = application_model.search([
            ('applicant_profile_id', '=', self.applicant_profile_id.id),
            ('program_id', '=', self.interested_program_id.id),
            ('state', 'not in', ['rejected', 'withdrawn']),
        ], limit=1)
        if duplicate_app:
            raise UserError(
                f'Applicant "{self.applicant_profile_id.full_name}" already has '
                f'an active application for "{self.interested_program_id.name}" '
                f'({duplicate_app.display_name}). Duplicate applications are not allowed.'
            )

        register = self._suggest_admission_register()
        vals = self._prepare_admission_application_vals(register=register)
        application = application_model.create(vals)

        self.write({
            'is_converted_to_application': True,
            'conversion_date': fields.Datetime.now(),
            'lead_education_status': 'converted',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Admission Application',
            'res_model': 'edu.admission.application',
            'res_id': application.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Duplicate Applicant Detection
    # ═════════════════════════════════════════════════════════════════════════

    def _find_duplicate_applicant_partners(self):
        """
        Returns res.partner records that may match this lead's contact info.
        Checks by email and mobile. Returns empty recordset if no match found.
        """
        self.ensure_one()
        domain_parts = []
        if self.email_from:
            domain_parts.append([('email', 'ilike', self.email_from)])
        if self.phone:
            domain_parts.append([('phone', '=', self.phone)])
        if not domain_parts:
            return self.env['res.partner']
        domain = expression.OR(domain_parts)
        return self.env['res.partner'].search(domain)

    def action_check_duplicate_applicants(self):
        """
        Opens a window listing potential duplicate contacts for review.
        Returns a success notification if no duplicates are found.
        """
        self.ensure_one()
        duplicates = self._find_duplicate_applicant_partners()
        if not duplicates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Duplicates Found',
                    'message': (
                        'No existing contacts match this lead\'s '
                        'email or mobile number.'
                    ),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'Potential Duplicate Contacts',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', duplicates.ids)],
            'target': 'new',
        }
