import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduClassroom(models.Model):
    """Extend edu.classroom with a continuous assessment count smart button."""

    _inherit = 'edu.classroom'

    assessment_record_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_record_count',
        store=False,
    )

    def _compute_assessment_record_count(self):
        groups = self.env['edu.continuous.assessment.record']._read_group(
            domain=[('classroom_id', 'in', self.ids)],
            groupby=['classroom_id'],
            aggregates=['__count'],
        )
        counts = {cl.id: cnt for cl, cnt in groups}
        for rec in self:
            rec.assessment_record_count = counts.get(rec.id, 0)

    def action_view_assessments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assessments — %s') % self.name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [('classroom_id', '=', self.id)],
            'context': {
                'default_classroom_id': self.id,
                'default_section_id': self.section_id.id,
                'default_subject_id': self.subject_id.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }
