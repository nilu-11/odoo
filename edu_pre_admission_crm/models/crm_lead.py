from odoo import _, api, fields, models
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
        [
            ('inquiry', 'Inquiry'),
            ('qualified', 'Qualified'),
            ('converted', 'Converted'),
            ('lost', 'Lost'),
        ],
        string='Education Status',
        default='inquiry',
        tracking=True,
        index=True,
        group_expand='_group_expand_lead_education_status',
    )

    # ── Timeline ──────────────────────────────────────────────────────────────
    inquiry_date = fields.Date(
        string='Inquiry Date',
        default=fields.Date.today,
        tracking=True,
        help='Date the first inquiry was received.',
    )
    inquiry_date_time = fields.Datetime(
        string='Inquiry DateTime',
        default=fields.Datetime.now,
        tracking=True,
        help='Date and time the first inquiry was received.',
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
        domain="['|', ('share', '=', False), ('share', '=', True)]",
        help='User responsible for counseling this prospect. Can be an internal or portal user.',
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
        string='Selected Program',
        tracking=True,
        ondelete='restrict',
        index=True,
        help='The final program selected for this applicant (set when marking Ready for Application).',
    )
    other_interested_program_ids = fields.Many2many(
        comodel_name='edu.program',
        string='Interested Programs',
        tracking=True,
        ondelete='restrict',
        index=True,
        help=(
            'Programs the applicant has expressed interest in. '
            'For example, if they are interested in both BCA and BBA.'
        ),
    )


    intended_academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        string='Intended Intake Year',
        tracking=True,
        ondelete='restrict',
        default=lambda self: self.env['edu.academic.year']._get_current_year(),
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
    qualification_id = fields.Many2one(
        comodel_name='edu.qualification',
        string='Qualification',
        tracking=True,
        ondelete='restrict',
        help='Select the highest qualification from the master list.',
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
    is_referral_source = fields.Boolean(
        compute='_compute_is_referral_source',
        string='Is Referral Source',
    )

    @api.depends('source_id')
    def _compute_is_referral_source(self):
        for rec in self:
            rec.is_referral_source = (
                bool(rec.source_id)
                and rec.source_id.name.strip().lower() == 'referral'
            )

    @api.depends('interaction_log_ids', 'interaction_log_ids.interaction_type',
                 'interaction_log_ids.date', 'interaction_log_ids.summary')
    def _compute_interaction_stats(self):
        for rec in self:
            logs = rec.interaction_log_ids
            rec.interaction_count = len(logs)
            rec.call_count = len(logs.filtered(lambda l: l.interaction_type == 'call'))
            rec.visit_count = len(logs.filtered(lambda l: l.interaction_type == 'campus_visit'))
            rec.session_count = len(logs.filtered(lambda l: l.interaction_type == 'counseling_session'))
            if logs:
                latest = logs.sorted('date', reverse=True)[0]
                rec.last_interaction_date = latest.date
                type_labels = dict(self.env['edu.interaction.log']._fields['interaction_type'].selection)
                type_label = type_labels.get(latest.interaction_type, latest.interaction_type)
                if latest.date:
                    delta = fields.Datetime.now() - latest.date
                    days = delta.days
                    if days == 0:
                        ago = 'today'
                    elif days == 1:
                        ago = 'yesterday'
                    else:
                        ago = f'{days}d ago'
                    rec.last_interaction_summary = f'{type_label} - {ago}'
                else:
                    rec.last_interaction_summary = type_label
                rec.days_since_last_interaction = (fields.Datetime.now() - latest.date).days if latest.date else 0
            else:
                rec.last_interaction_date = False
                rec.last_interaction_summary = False
                rec.days_since_last_interaction = 0

    @api.depends('activity_ids', 'activity_ids.date_deadline',
                 'activity_ids.activity_type_id', 'activity_ids.summary')
    def _compute_next_activity_summary(self):
        for rec in self:
            upcoming = rec.activity_ids.sorted('date_deadline')
            if upcoming:
                act = upcoming[0]
                name = act.summary or act.activity_type_id.name or 'Activity'
                delta = (act.date_deadline - fields.Date.today()).days
                if delta == 0:
                    when = 'Today'
                elif delta == 1:
                    when = 'Tomorrow'
                elif delta < 0:
                    when = f'{abs(delta)}d overdue'
                else:
                    when = f'in {delta}d'
                rec.next_activity_summary = f'{name} - {when}'
            else:
                rec.next_activity_summary = False

    @api.depends('lead_education_status', 'applicant_profile_id',
                 'interested_program_id', 'interaction_count',
                 'is_converted_to_application', 'profile_completeness')
    def _compute_next_step_banner(self):
        for rec in self:
            if rec.lead_education_status == 'converted' or rec.is_converted_to_application:
                rec.next_step_banner = False
                continue
            if rec.lead_education_status == 'inquiry':
                if not rec.applicant_profile_id:
                    msg = 'Create an applicant profile to proceed'
                    icon = 'fa-user-plus'
                elif not rec.interested_program_id:
                    msg = 'Select a program of interest'
                    icon = 'fa-graduation-cap'
                elif rec.interaction_count == 0:
                    msg = 'Schedule a follow-up call or campus visit'
                    icon = 'fa-phone'
                else:
                    msg = 'Ready to qualify — review and click Qualify'
                    icon = 'fa-check-circle'
            elif rec.lead_education_status == 'qualified':
                pct = rec.profile_completeness or 0
                msg = f'Review profile completeness ({pct}%), then Convert to Application'
                icon = 'fa-arrow-right'
            else:
                rec.next_step_banner = False
                continue
            rec.next_step_banner = (
                f'<div class="alert alert-info py-2 px-3 mb-0 d-flex align-items-center">'
                f'<i class="fa {icon} me-2"/><span>{msg}</span></div>'
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

    # ── Interaction Log ──────────────────────────────────────────────────────
    interaction_log_ids = fields.One2many(
        comodel_name='edu.interaction.log',
        inverse_name='lead_id',
        string='Interactions',
    )
    interaction_count = fields.Integer(
        string='Interactions',
        compute='_compute_interaction_stats',
        store=True,
    )
    last_interaction_date = fields.Datetime(
        string='Last Interaction',
        compute='_compute_interaction_stats',
        store=True,
    )
    last_interaction_summary = fields.Char(
        string='Last Interaction Summary',
        compute='_compute_interaction_stats',
    )
    days_since_last_interaction = fields.Integer(
        string='Days Since Last Interaction',
        compute='_compute_interaction_stats',
    )
    call_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    visit_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    session_count = fields.Integer(
        compute='_compute_interaction_stats',
        store=True,
    )
    next_activity_summary = fields.Char(
        string='Next Activity',
        compute='_compute_next_activity_summary',
    )
    profile_completeness = fields.Integer(
        related='applicant_profile_id.profile_completeness',
        string='Profile Completeness',
    )
    next_step_banner = fields.Html(
        string='Next Step',
        compute='_compute_next_step_banner',
        sanitize=False,
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

    # ── Computed: duplicate lead detection ────────────────────────────────────
    duplicate_phone_lead_ids = fields.Many2many(
        comodel_name='crm.lead',
        compute='_compute_duplicate_leads',
        string='Leads with Same Phone',
    )
    duplicate_email_lead_ids = fields.Many2many(
        comodel_name='crm.lead',
        compute='_compute_duplicate_leads',
        string='Leads with Same Email',
    )
    has_duplicate_phone = fields.Boolean(compute='_compute_duplicate_leads')
    has_duplicate_email = fields.Boolean(compute='_compute_duplicate_leads')
    is_duplicate = fields.Boolean(compute='_compute_duplicate_leads')
    duplicate_lead_count = fields.Integer(
        compute='_compute_duplicate_leads',
        string='Similar Inquiries',
    )

    @api.depends('phone', 'email_from')
    def _compute_duplicate_leads(self):
        for rec in self:
            if rec.phone:
                phone_dupes = self.search([
                    ('phone', '=', rec.phone),
                    ('id', '!=', rec.id),
                    ('id', '<', rec.id),
                ])
                rec.duplicate_phone_lead_ids = phone_dupes
                rec.has_duplicate_phone = bool(phone_dupes)
            else:
                phone_dupes = self.env['crm.lead']
                rec.duplicate_phone_lead_ids = phone_dupes
                rec.has_duplicate_phone = False
            if rec.email_from:
                email_dupes = self.search([
                    ('email_from', '=ilike', rec.email_from),
                    ('id', '!=', rec.id),
                    ('id', '<', rec.id),
                ])
                rec.duplicate_email_lead_ids = email_dupes
                rec.has_duplicate_email = bool(email_dupes)
            else:
                email_dupes = self.env['crm.lead']
                rec.duplicate_email_lead_ids = email_dupes
                rec.has_duplicate_email = False
            rec.is_duplicate = rec.has_duplicate_phone or rec.has_duplicate_email
            rec.duplicate_lead_count = len(phone_dupes | email_dupes)

    @api.depends('activity_ids', 'message_ids')
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
            # Auto-assign counselor from sales team
            if not vals.get('counselor_id'):
                team_id = vals.get('team_id')
                if team_id:
                    team = self.env['crm.team'].browse(team_id)
                    if team.user_id:
                        vals['counselor_id'] = team.user_id.id
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
        return ['inquiry', 'qualified', 'converted', 'lost']

    # ═══════════════════════════════════════════════════════════════════════════    # Education Status Transitions
    # ═════════════════════════════════════════════════════════════════════════

    def action_set_qualified(self):
        """Qualify the lead. Auto-creates applicant profile if needed."""
        self.ensure_one()
        if self.lead_education_status not in ('inquiry',):
            raise UserError(_("Only inquiries can be qualified."))
        # Auto-create profile from quick name if needed
        if not self.applicant_profile_id and self.quick_applicant_name:
            self._create_profile_from_quick_name()
        if not self.applicant_profile_id:
            raise UserError(_("An applicant profile is required to qualify this lead."))
        if not self.interested_program_id:
            raise UserError(_("A program of interest is required."))
        self.lead_education_status = 'qualified'

    # ═════════════════════════════════════════════════════════════════════════
    # Conversion to Admission Application
    # ═════════════════════════════════════════════════════════════════════════

    def _check_conversion_readiness(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("A contact is required."))
        if not self.applicant_profile_id:
            raise UserError(_("An applicant profile is required."))
        if not self.interested_program_id:
            raise UserError(_("A program of interest is required."))
        if self.is_converted_to_application:
            raise UserError(_("This lead has already been converted to an application."))
        completeness = self.applicant_profile_id.profile_completeness or 0
        if completeness < 60:
            raise UserError(
                _(
                    "Applicant profile is only %(pct)s%% complete. "
                    "At least 60%% is required before conversion.",
                    pct=completeness,
                )
            )

    @api.constrains('phone', 'email_from')
    def _check_phone_or_email(self):
        for rec in self:
            if not rec.phone and not rec.email_from:
                raise UserError(
                    _("At least a phone number or email address is required.")
                )

    def _suggest_admission_register(self):
        """
        Attempts to find an open admission register for this lead's program/year.
        Returns the register record or None.

        Tries progressively more lenient matches:
          1. Program + year + preferred batch (strictest)
          2. Program + year
          3. Program only (any open register)

        Requires edu_admission to be installed.
        """
        self.ensure_one()
        register_model = self.env.get('edu.admission.register')
        if not register_model or not self.interested_program_id:
            return None
        base_domain = [
            ('program_id', '=', self.interested_program_id.id),
            ('state', '=', 'open'),
        ]
        # 1. Strict: year + batch
        if self.intended_academic_year_id and self.preferred_batch_id:
            reg = register_model.search(
                base_domain + [
                    ('academic_year_id', '=', self.intended_academic_year_id.id),
                    ('batch_id', '=', self.preferred_batch_id.id),
                ],
                limit=1,
            )
            if reg:
                return reg
        # 2. Program + year
        if self.intended_academic_year_id:
            reg = register_model.search(
                base_domain + [
                    ('academic_year_id', '=', self.intended_academic_year_id.id),
                ],
                limit=1,
            )
            if reg:
                return reg
        # 3. Program only
        return register_model.search(base_domain, limit=1) or None

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

    def action_open_merge_wizard(self):
        self.ensure_one()
        duplicates = self.duplicate_phone_lead_ids | self.duplicate_email_lead_ids
        if not duplicates:
            raise UserError(_("No duplicate leads detected."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Merge Duplicate Lead'),
            'res_model': 'edu.lead.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_duplicate_lead_id': duplicates[0].id,
            },
        }

    def action_open_similar_inquiries(self):
        """
        Opens a list of CRM leads that share the same phone or email as this lead.
        """
        self.ensure_one()
        all_dupes = self.duplicate_phone_lead_ids | self.duplicate_email_lead_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Similar Inquiries',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_dupes.ids)],
            'target': 'new',
        }

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

    def action_quick_schedule(self):
        """Open activity scheduling dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Activity'),
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'crm.lead',
                'default_res_id': self.id,
                'default_user_id': self.counselor_id.id or self.env.uid,
            },
        }

    def action_log_interaction(self):
        """Open form to manually log an interaction, auto-linking the earliest open activity."""
        self.ensure_one()
        ctx = {
            'default_lead_id': self.id,
            'default_counselor_id': self.env.uid,
        }
        # Auto-select the earliest open activity on this lead
        earliest = self.activity_ids.sorted('date_deadline')[:1]
        if earliest:
            ctx['default_activity_id'] = earliest.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Interaction'),
            'res_model': 'edu.interaction.log',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_open_applicant_profile(self):
        """Open the linked applicant profile form."""
        self.ensure_one()
        if not self.applicant_profile_id:
            raise UserError(_("No applicant profile linked to this lead."))
        return {
            'type': 'ir.actions.act_window',
            'name': self.applicant_profile_id.full_name,
            'res_model': 'edu.applicant.profile',
            'res_id': self.applicant_profile_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
