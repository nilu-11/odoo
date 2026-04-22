from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ── Portal role (computed) ─────────────────────────────────────────────────

    portal_role = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('teacher', 'Teacher'),
            ('multi', 'Multiple Roles'),
            ('none', 'None'),
        ],
        string='Portal Role',
        compute='_compute_portal_role',
        store=False,
        help='Derived from edu_portal security groups assigned to this user.',
    )

    # ── Parent helper: children partner IDs ────────────────────────────────────

    children_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Children Partners',
        compute='_compute_children_partner_ids',
        store=False,
        help='Partner IDs of children linked to this parent (for record-rule scoping).',
    )

    # ── Stream visibility: sections the user can see posts for ─────────────────

    stream_visible_section_ids = fields.Many2many(
        comodel_name='edu.section',
        string='Visible Sections',
        compute='_compute_stream_visible_section_ids',
        store=False,
        help='Sections whose classroom posts are visible to this portal user.',
    )

    # ── Computed: portal_role ──────────────────────────────────────────────────

    def _compute_portal_role(self):
        student_group = self.env.ref(
            'edu_portal.group_edu_portal_student', raise_if_not_found=False,
        )
        parent_group = self.env.ref(
            'edu_portal.group_edu_portal_parent', raise_if_not_found=False,
        )
        teacher_group = self.env.ref(
            'edu_portal.group_edu_portal_teacher', raise_if_not_found=False,
        )
        for user in self:
            roles = []
            if student_group and user.has_group('edu_portal.group_edu_portal_student'):
                roles.append('student')
            if parent_group and user.has_group('edu_portal.group_edu_portal_parent'):
                roles.append('parent')
            if teacher_group and user.has_group('edu_portal.group_edu_portal_teacher'):
                roles.append('teacher')
            if len(roles) > 1:
                user.portal_role = 'multi'
            elif len(roles) == 1:
                user.portal_role = roles[0]
            else:
                user.portal_role = 'none'

    # ── Computed: children_partner_ids ──────────────────────────────────────────

    def _compute_children_partner_ids(self):
        """For parent-portal users, find children's partner IDs via guardian linkage.

        Path: res.users -> res.partner -> edu.guardian (partner_id)
              -> edu.applicant.guardian.rel (guardian_id)
              -> edu.applicant.profile -> edu.student -> res.partner
        """
        GuardianRel = self.env['edu.applicant.guardian.rel'].sudo()
        Guardian = self.env['edu.guardian'].sudo()
        Student = self.env['edu.student'].sudo()

        for user in self:
            if not user.has_group('edu_portal.group_edu_portal_parent'):
                user.children_partner_ids = self.env['res.partner']
                continue

            # Find guardian record for this user's partner
            guardian = Guardian.search([
                ('partner_id', '=', user.sudo().partner_id.id),
            ], limit=1)
            if not guardian:
                user.children_partner_ids = self.env['res.partner']
                continue

            # Find all applicant profiles linked to this guardian
            rels = GuardianRel.search([
                ('guardian_id', '=', guardian.id),
                ('active', '=', True),
            ])
            applicant_profile_ids = rels.mapped('applicant_profile_id').ids

            # Find students whose applicant_profile_id is in that set
            students = Student.search([
                ('applicant_profile_id', 'in', applicant_profile_ids),
            ])
            user.children_partner_ids = students.mapped('partner_id')

    # ── Computed: stream_visible_section_ids ───────────────────────────────────

    def _compute_stream_visible_section_ids(self):
        """Sections this user can see posts from.

        - Student: sections from their active progression history.
        - Parent: union of children's sections.
        - Teacher: sections of classrooms they teach.
        """
        Student = self.env['edu.student'].sudo()
        ProgressionHistory = self.env['edu.student.progression.history'].sudo()
        Classroom = self.env['edu.classroom'].sudo()
        Section = self.env['edu.section']

        for user in self:
            section_ids = set()

            # Student
            if user.has_group('edu_portal.group_edu_portal_student'):
                student = Student.search([
                    ('partner_id', '=', user.sudo().partner_id.id),
                ], limit=1)
                if student:
                    histories = ProgressionHistory.search([
                        ('student_id', '=', student.id),
                        ('state', '=', 'active'),
                    ])
                    section_ids.update(histories.mapped('section_id').ids)

            # Parent
            if user.has_group('edu_portal.group_edu_portal_parent'):
                child_partners = user.children_partner_ids
                if child_partners:
                    children = Student.search([
                        ('partner_id', 'in', child_partners.ids),
                    ])
                    for child in children:
                        histories = ProgressionHistory.search([
                            ('student_id', '=', child.id),
                            ('state', '=', 'active'),
                        ])
                        section_ids.update(histories.mapped('section_id').ids)

            # Teacher
            if user.has_group('edu_portal.group_edu_portal_teacher'):
                classrooms = Classroom.search([
                    ('teacher_id', '=', user.id),
                    ('state', '=', 'active'),
                ])
                section_ids.update(classrooms.mapped('section_id').ids)

            user.stream_visible_section_ids = Section.browse(list(section_ids))
