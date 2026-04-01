from odoo import api, fields, models


class EduSection(models.Model):
    """Extend edu.section with a live student count derived from progression history.

    This count is the authoritative source for capacity enforcement in the
    section assignment wizard. It is not stored — it is always recomputed
    live from active progression history records.
    """

    _inherit = 'edu.section'

    # ── Live student count ────────────────────────────────────────────────────

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
