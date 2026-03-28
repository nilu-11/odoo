import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduClassroom(models.Model):
    """Extend edu.classroom with exam paper count and smart button."""

    _inherit = 'edu.classroom'

    exam_paper_count = fields.Integer(
        string='Exam Papers',
        compute='_compute_exam_paper_count',
        store=False,
    )

    def _compute_exam_paper_count(self):
        groups = self.env['edu.exam.paper']._read_group(
            domain=[('classroom_id', 'in', self.ids)],
            groupby=['classroom_id'],
            aggregates=['__count'],
        )
        counts = {classroom.id: cnt for classroom, cnt in groups}
        for rec in self:
            rec.exam_paper_count = counts.get(rec.id, 0)

    def action_view_exam_papers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Papers — %s') % self.name,
            'res_model': 'edu.exam.paper',
            'view_mode': 'list,form',
            'domain': [('classroom_id', '=', self.id)],
            'context': {
                'default_classroom_id': self.id,
                'default_section_id': self.section_id.id,
                'default_curriculum_line_id': self.curriculum_line_id.id,
                'default_program_term_id': self.program_term_id.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }
