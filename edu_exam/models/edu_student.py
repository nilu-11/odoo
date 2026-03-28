import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduStudent(models.Model):
    """Extend edu.student with exam marksheet count and smart button."""

    _inherit = 'edu.student'

    exam_marksheet_count = fields.Integer(
        string='Exam Marksheets',
        compute='_compute_exam_marksheet_count',
        store=False,
    )

    def _compute_exam_marksheet_count(self):
        groups = self.env['edu.exam.marksheet']._read_group(
            domain=[('student_id', 'in', self.ids)],
            groupby=['student_id'],
            aggregates=['__count'],
        )
        counts = {student.id: cnt for student, cnt in groups}
        for rec in self:
            rec.exam_marksheet_count = counts.get(rec.id, 0)

    def action_view_exam_marksheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Marksheets — %s') % self.display_name,
            'res_model': 'edu.exam.marksheet',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
