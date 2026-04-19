from odoo import api, fields, models


class EduGuardian(models.Model):
    """
    Structured guardian/parent entity.

    A guardian can be linked to multiple applicants (and future students) via
    edu.applicant.guardian.rel. One partner can hold only one guardian record —
    the UNIQUE(partner_id) constraint enforces this.

    Future use:
    - guardian.partner_id → parent portal login
    - view all linked children and their fee statements
    - financial contact for invoicing
    """

    _name = 'edu.guardian'
    _description = 'Guardian'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'last_name, first_name, id'
    _rec_name = 'full_name'

    # ── Identity ──────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
        ondelete='restrict',
        tracking=True,
        index=True,
        help=(
            'Auto-created from guardian name on save. '
            'Used for portal access and fee payment notifications.'
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

    # ── Contact (surfaced from res.partner) ────────────────────────────────────
    phone = fields.Char(related='partner_id.phone', string='Phone', readonly=False)
    email = fields.Char(related='partner_id.email', string='Email', readonly=False)

    # ── Professional ──────────────────────────────────────────────────────────
    occupation = fields.Char(string='Occupation', tracking=True)
    organization = fields.Char(string='Organization / Employer', tracking=True)

    # ── Role flags ────────────────────────────────────────────────────────────
    is_emergency_contact = fields.Boolean(
        string='Emergency Contact',
        default=False,
        help='Default emergency contact for all linked applicants.',
    )
    is_financial_contact = fields.Boolean(
        string='Financial Contact',
        default=False,
        help='Responsible for fee payments. Used for invoice routing.',
    )
    is_legal_guardian = fields.Boolean(
        string='Legal Guardian',
        default=False,
        help='Has formal legal guardianship.',
    )

    # ── Linked applicants ─────────────────────────────────────────────────────
    applicant_rel_ids = fields.One2many(
        comodel_name='edu.applicant.guardian.rel',
        inverse_name='guardian_id',
        string='Linked Applicants',
    )
    applicant_count = fields.Integer(
        string='Applicants',
        compute='_compute_applicant_count',
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
            'A guardian record already exists for this contact.',
        ),
    ]

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('first_name', 'middle_name', 'last_name')
    def _compute_full_name(self):
        for rec in self:
            parts = [rec.first_name, rec.middle_name, rec.last_name]
            rec.full_name = ' '.join(p for p in parts if p)

    @api.depends('applicant_rel_ids')
    def _compute_applicant_count(self):
        data = self.env['edu.applicant.guardian.rel']._read_group(
            [('guardian_id', 'in', self.ids), ('active', '=', True)],
            ['guardian_id'],
            ['__count'],
        )
        mapped = {g.id: count for g, count in data}
        for rec in self:
            rec.applicant_count = mapped.get(rec.id, 0)

    # ── Partner sync ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        partner_model = self.env['res.partner'].sudo()
        for vals in vals_list:
            if not vals.get('partner_id'):
                name_parts = [
                    vals.get('first_name'),
                    vals.get('middle_name'),
                    vals.get('last_name'),
                ]
                partner_name = ' '.join(p for p in name_parts if p) or 'Guardian'
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

    # ── Smart button action ───────────────────────────────────────────────────
    def action_view_applicants(self):
        self.ensure_one()
        applicant_ids = self.applicant_rel_ids.mapped('applicant_profile_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': f'Applicants — {self.full_name}',
            'res_model': 'edu.applicant.profile',
            'view_mode': 'list,form',
            'domain': [('id', 'in', applicant_ids)],
        }
