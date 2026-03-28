import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduStudent(models.Model):
    """Extend edu.student with a continuous assessment history smart button."""

    _inherit = 'edu.student'

    continuous_assessment_count = fields.Integer(
        string='Assessments',
        compute='_compute_continuous_assessment_count',
        store=False,
    )

    def _compute_continuous_assessment_count(self):
        groups = self.env['edu.continuous.assessment.record']._read_group(
            domain=[('student_id', 'in', self.ids)],
            groupby=['student_id'],
            aggregates=['__count'],
        )
        counts = {st.id: cnt for st, cnt in groups}
        for rec in self:
            rec.continuous_assessment_count = counts.get(rec.id, 0)

    def action_view_assessments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Continuous Assessments — %s') % self.display_name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
            },
        }
