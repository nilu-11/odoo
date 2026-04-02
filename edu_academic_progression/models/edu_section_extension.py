from odoo import api, fields, models, _


class EduSection(models.Model):
    """Extend edu.section with live student count and student navigation."""

    _inherit = 'edu.section'

    # ── Students (computed from progression history — the authoritative source)

    student_ids = fields.Many2many(
        'edu.student',
        string='Students',
        compute='_compute_student_ids',
        store=False,
    )

    def _compute_student_ids(self):
        if not self.ids:
            for rec in self:
                rec.student_ids = False
            return
        histories = self.env['edu.student.progression.history'].search([
            ('section_id', 'in', self.ids),
            ('state', '=', 'active'),
        ])
        # group by section
        section_map = {}
        for h in histories:
            section_map.setdefault(h.section_id.id, []).append(h.student_id.id)
        for rec in self:
            rec.student_ids = section_map.get(rec.id, [])

    # ── Live student count (via progression history — authoritative) ──────────

    current_student_count = fields.Integer(
        string='Enrolled Students',
        compute='_compute_current_student_count',
        store=False,
        help='Number of students with an active progression history record '
             'assigned to this section. Used for capacity enforcement.',
    )

    def _compute_current_student_count(self):
        if not self.ids:
            for rec in self:
                rec.current_student_count = 0
            return
        data = self.env['edu.student.progression.history']._read_group(
            domain=[
                ('section_id', 'in', self.ids),
                ('state', '=', 'active'),
            ],
            groupby=['section_id'],
            aggregates=['__count'],
        )
        mapped = {section.id: count for section, count in data}
        for rec in self:
            rec.current_student_count = mapped.get(rec.id, 0)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_view_students(self):
        """Open student list for this section via progression history."""
        self.ensure_one()
        histories = self.env['edu.student.progression.history'].search([
            ('section_id', '=', self.id),
            ('state', '=', 'active'),
        ])
        student_ids = histories.mapped('student_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Students — %s') % self.full_label,
            'res_model': 'edu.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', student_ids)],
        }

    def action_view_progression_history(self):
        """Open progression histories for this section."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progression — %s') % self.full_label,
            'res_model': 'edu.student.progression.history',
            'view_mode': 'list,form',
            'domain': [
                ('section_id', '=', self.id),
                ('state', '=', 'active'),
            ],
        }
