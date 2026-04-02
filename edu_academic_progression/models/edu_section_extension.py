from odoo import api, fields, models, _


class EduSection(models.Model):
    """Extend edu.section with live student count and student navigation."""

    _inherit = 'edu.section'

    # ── Students in this section (via student.section_id inverse) ────────────

    student_ids = fields.One2many(
        'edu.student', 'section_id',
        string='Students',
    )

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
        """Open the student list filtered to students in this section."""
        self.ensure_one()
        # Student records carry section_id directly (updated by progression)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Students — %s') % self.full_label,
            'res_model': 'edu.student',
            'view_mode': 'list,form',
            'domain': [('section_id', '=', self.id)],
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
