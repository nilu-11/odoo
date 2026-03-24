from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EduApplicantGuardianRel(models.Model):
    """
    Relationship record linking one applicant to one guardian.

    Keeps relationship type, role flags, and living arrangement per applicant–guardian
    pair. A guardian can be linked to multiple applicants (siblings, future students).
    One applicant can have multiple guardians (father + mother + sponsor).

    Future use:
    - Sibling detection: same guardian_id linked to multiple applicants
    - Financial routing: is_financial_contact → invoice to this guardian's partner
    - Portal: guardian.partner_id sees all their linked applicants/students
    """

    _name = 'edu.applicant.guardian.rel'
    _description = 'Applicant–Guardian Relationship'
    _order = 'applicant_profile_id, sequence, id'
    _rec_name = 'guardian_id'

    # ── Core FKs ──────────────────────────────────────────────────────────────
    applicant_profile_id = fields.Many2one(
        comodel_name='edu.applicant.profile',
        string='Applicant',
        required=True,
        ondelete='cascade',
        index=True,
    )
    guardian_id = fields.Many2one(
        comodel_name='edu.guardian',
        string='Guardian',
        required=True,
        ondelete='restrict',
        index=True,
    )
    relationship_type_id = fields.Many2one(
        comodel_name='edu.relationship.type',
        string='Relationship',
        required=True,
        ondelete='restrict',
    )

    # ── Role flags (per applicant, may differ from guardian defaults) ─────────
    is_primary = fields.Boolean(
        string='Primary Guardian',
        default=False,
        help='Primary point of contact for this applicant. Only one per applicant.',
    )
    is_emergency_contact = fields.Boolean(
        string='Emergency Contact',
        default=False,
    )
    is_financial_contact = fields.Boolean(
        string='Financial Contact',
        default=False,
        help='Responsible for fee payments for this applicant.',
    )
    lives_with_applicant = fields.Boolean(
        string='Lives With Applicant',
        default=False,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    # ── Convenience related fields ────────────────────────────────────────────
    guardian_partner_id = fields.Many2one(
        related='guardian_id.partner_id',
        string='Guardian Contact',
        store=False,
    )
    guardian_occupation = fields.Char(
        related='guardian_id.occupation',
        string='Occupation',
        store=False,
    )
    guardian_organization = fields.Char(
        related='guardian_id.organization',
        string='Organization',
        store=False,
    )

    # ── SQL constraints ───────────────────────────────────────────────────────
    _sql_constraints = [
        (
            'applicant_guardian_unique',
            'UNIQUE(applicant_profile_id, guardian_id)',
            'This guardian is already linked to this applicant.',
        ),
    ]

    # ── Python constraints ────────────────────────────────────────────────────
    @api.constrains('is_primary', 'applicant_profile_id')
    def _check_single_primary(self):
        for rec in self:
            if not rec.is_primary:
                continue
            duplicate_primary = self.search([
                ('applicant_profile_id', '=', rec.applicant_profile_id.id),
                ('is_primary', '=', True),
                ('id', '!=', rec.id),
                ('active', 'in', [True, False]),
            ])
            if duplicate_primary:
                raise ValidationError(
                    f'Applicant "{rec.applicant_profile_id.full_name}" '
                    f'already has a primary guardian '
                    f'("{duplicate_primary[0].guardian_id.full_name}"). '
                    'Only one primary guardian is allowed per applicant.'
                )
