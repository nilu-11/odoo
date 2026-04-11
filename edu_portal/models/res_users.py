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

    # ═══ Stream-visible Sections (for classroom post record rules) ═══

    stream_visible_section_ids = fields.Many2many(
        comodel_name='edu.section',
        relation='res_users_stream_section_rel',
        column1='user_id',
        column2='section_id',
        string='Stream Visible Sections',
        compute='_compute_stream_visible_section_ids',
        store=False,
        help='Sections this user can read classroom stream posts for. '
             'For students: the section of their active progression history. '
             'For parents: the sections of all their children. '
             'Used by edu.classroom.post record rules.',
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

    def _compute_stream_visible_section_ids(self):
        """Sections whose classroom posts this user can read.

        Students → their own active progression history section.
        Parents → their children's active progression history sections.
        Everyone else → empty (teachers use a separate record rule
        based on classroom ownership).
        """
        Student = self.env['edu.student'].sudo()
        History = self.env['edu.student.progression.history'].sudo()
        for user in self:
            section_ids = set()
            if not user.partner_id:
                user.stream_visible_section_ids = [(5, 0, 0)]
                continue
            # Student's own section
            students = Student.search([('partner_id', '=', user.partner_id.id)])
            if students:
                histories = History.search([
                    ('student_id', 'in', students.ids),
                    ('state', '=', 'active'),
                ])
                section_ids.update(histories.mapped('section_id').ids)
            # Parent: children's sections
            if user.children_partner_ids:
                children = Student.search([
                    ('partner_id', 'in', user.children_partner_ids.ids),
                ])
                if children:
                    histories = History.search([
                        ('student_id', 'in', children.ids),
                        ('state', '=', 'active'),
                    ])
                    section_ids.update(histories.mapped('section_id').ids)
            user.stream_visible_section_ids = [(6, 0, list(section_ids))]

    # ═══ Login Redirect Override ═══

    def _get_portal_landing_url(self):
        """Return landing URL for portal users after login."""
        self.ensure_one()
        if self.portal_role in ('student', 'parent', 'teacher', 'multi'):
            return '/portal'
        return False
