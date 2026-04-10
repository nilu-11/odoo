from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ═══ Portal Role ═══

    portal_role = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('teacher', 'Teacher'),
            ('multi', 'Multiple Roles'),
            ('none', 'No Portal Role'),
        ],
        string='Portal Role',
        compute='_compute_portal_role',
    )

    # ═══ Parent's Children (for record rule scoping) ═══

    children_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='res_users_children_partner_rel',
        column1='user_id',
        column2='partner_id',
        string='Children Partners',
        compute='_compute_children_partner_ids',
        store=False,
        help='Partner records of children (students) linked to this parent via guardian relationship. '
             'Used by parent portal record rules to scope access.',
    )

    # ═══ Computed Methods ═══

    def _compute_portal_role(self):
        for user in self:
            roles = []
            if user.has_group('edu_portal.group_edu_portal_student'):
                roles.append('student')
            if user.has_group('edu_portal.group_edu_portal_parent'):
                roles.append('parent')
            if user.has_group('edu_portal.group_edu_portal_teacher'):
                roles.append('teacher')
            if len(roles) == 0:
                user.portal_role = 'none'
            elif len(roles) == 1:
                user.portal_role = roles[0]
            else:
                user.portal_role = 'multi'

    def _compute_children_partner_ids(self):
        Guardian = self.env['edu.guardian'].sudo()
        Student = self.env['edu.student'].sudo()
        for user in self:
            if not user.partner_id:
                user.children_partner_ids = [(5, 0, 0)]
                continue
            guardian = Guardian.search([('partner_id', '=', user.partner_id.id)], limit=1)
            if not guardian:
                user.children_partner_ids = [(5, 0, 0)]
                continue
            applicant_profiles = guardian.applicant_ids.mapped('applicant_id')
            students = Student.search([
                ('applicant_profile_id', 'in', applicant_profiles.ids),
            ])
            user.children_partner_ids = [(6, 0, students.mapped('partner_id').ids)]

    # ═══ Login Redirect Override ═══

    def _get_portal_landing_url(self):
        """Return landing URL for portal users after login."""
        self.ensure_one()
        if self.portal_role in ('student', 'parent', 'teacher', 'multi'):
            return '/portal'
        return False
