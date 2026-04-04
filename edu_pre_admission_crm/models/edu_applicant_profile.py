from datetime import date

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduApplicantProfile(models.Model):
    """
    Structured pre-student identity record.

    Design principles:
    - res.partner is the identity layer (name, email, phone, address, portal access).
    - This model is the EMIS role layer: demographics, relationships, academic history.
    - Designed for direct reuse as the base of a future edu.student record.
      (future: student.partner_id = applicant.partner_id, student.applicant_profile_id = applicant.id)
    """

    _name = 'edu.applicant.profile'
    _description = 'Applicant Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'last_name, first_name, id'
    _rec_name = 'full_name'

    # ── Identity ──────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help=(
            'The res.partner record that serves as the identity layer. '
            'Holds name, email, phone, and address. '
            'Used for portal access and system communication.'
        ),
    )

    first_name = fields.Char(string='First Name', required=True, tracking=True)
    middle_name = fields.Char(string='Middle Name', tracking=True)
    last_name = fields.Char(string='Last Name', required=True, tracking=True)
    full_name = fields.Char(
        string='Full Name',
        compute='_compute_full_name',
        store=True,
        index=True,
    )

    # ── Demographics ──────────────────────────────────────────────────────────
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
            ('prefer_not_to_say', 'Prefer Not to Say'),
        ],
        string='Gender',
        tracking=True,
    )
    date_of_birth = fields.Date(string='Date of Birth', tracking=True)
    age = fields.Integer(string='Age', compute='_compute_age')
    nationality_id = fields.Many2one(
        comodel_name='res.country',
        string='Nationality',
        tracking=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    guardian_rel_ids = fields.One2many(
        comodel_name='edu.applicant.guardian.rel',
        inverse_name='applicant_profile_id',
        string='Guardians',
    )
    academic_history_ids = fields.One2many(
        comodel_name='edu.applicant.academic.history',
        inverse_name='applicant_profile_id',
        string='Academic History',
    )

    # ── Smart button: CRM leads ───────────────────────────────────────────────
    lead_count = fields.Integer(
        string='CRM Leads',
        compute='_compute_lead_count',
    )

    # ── System ────────────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'partner_unique',
            'UNIQUE(partner_id)',
            'An applicant profile already exists for this contact.',
        ),
    ]

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('first_name', 'middle_name', 'last_name')
    def _compute_full_name(self):
        for rec in self:
            parts = [rec.first_name, rec.middle_name, rec.last_name]
            rec.full_name = ' '.join(p for p in parts if p)

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.date_of_birth:
                rec.age = relativedelta(today, rec.date_of_birth).years
            else:
                rec.age = 0

    @api.depends()
    def _compute_lead_count(self):
        lead_model = self.env.get('crm.lead')
        if not lead_model:
            for rec in self:
                rec.lead_count = 0
            return
        data = lead_model._read_group(
            [('applicant_profile_id', 'in', self.ids)],
            ['applicant_profile_id'],
            ['__count'],
        )
        mapped = {p.id: count for p, count in data}
        for rec in self:
            rec.lead_count = mapped.get(rec.id, 0)

    # ── Partner sync ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        partner_model = self.env['res.partner'].sudo()
        for vals in vals_list:
            # Always create a dedicated new contact for each applicant.
            name_parts = [
                vals.get('first_name'),
                vals.get('middle_name'),
                vals.get('last_name'),
            ]
            partner_name = ' '.join(p for p in name_parts if p) or 'Applicant'
            partner = partner_model.create({
                'name': partner_name,
                'company_type': 'person',
            })
            vals['partner_id'] = partner.id
        records = super().create(vals_list)
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('first_name', 'middle_name', 'last_name')):
            for rec in self:
                if rec.partner_id and rec.full_name:
                    rec.partner_id.sudo().write({'name': rec.full_name})
        return res

    # ── Python constraints ────────────────────────────────────────────────────
    @api.constrains('partner_id')
    def _check_partner_unique(self):
        for rec in self:
            if not rec.partner_id:
                raise ValidationError(
                    f'Applicant "{rec.full_name}" must have a linked contact.'
                )
            duplicate = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'Contact "{rec.partner_id.name}" is already linked to '
                    f'applicant "{duplicate.full_name}". '
                    'Each applicant must have a dedicated contact.'
                )

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        today = date.today()
        for rec in self:
            if rec.date_of_birth and rec.date_of_birth > today:
                raise ValidationError(
                    f'Date of birth cannot be in the future '
                    f'(applicant: "{rec.full_name}").'
                )

    # ── Smart button action ───────────────────────────────────────────────────
    def action_view_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'CRM Leads — {self.full_name}',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('applicant_profile_id', '=', self.id)],
            'context': {'default_applicant_profile_id': self.id},
        }
