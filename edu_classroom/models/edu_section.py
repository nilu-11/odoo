from odoo import api, fields, models, _


class EduSection(models.Model):
    """Extend edu.section with classroom counts and actions."""

    _inherit = 'edu.section'

    # ── Classroom counts ──────────────────────────────────────────────────────

    classroom_count = fields.Integer(
        string='Classrooms',
        compute='_compute_classroom_count',
        store=False,
    )

    def _compute_classroom_count(self):
        Classroom = self.env['edu.classroom']
        data = Classroom._read_group(
            domain=[('section_id', 'in', self.ids)],
            groupby=['section_id'],
            aggregates=['__count'],
        )
        mapped = {section.id: count for section, count in data}
        for rec in self:
            rec.classroom_count = mapped.get(rec.id, 0)

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_classrooms(self):
        """Open classroom list filtered to this section."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Classrooms — %s') % self.full_label,
            'res_model': 'edu.classroom',
            'view_mode': 'list,form',
            'domain': [('section_id', '=', self.id)],
            'context': {
                'default_batch_id': self.batch_id.id,
                'default_section_id': self.id,
            },
        }
