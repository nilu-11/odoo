import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduBatch(models.Model):
    """Extend edu.batch with exam session count and smart button."""

    _inherit = 'edu.batch'

    exam_session_count = fields.Integer(
        string='Exam Sessions',
        compute='_compute_exam_session_count',
        store=False,
    )

    def _compute_exam_session_count(self):
        groups = self.env['edu.exam.session']._read_group(
            domain=[('batch_id', 'in', self.ids)],
            groupby=['batch_id'],
            aggregates=['__count'],
        )
        counts = {batch.id: cnt for batch, cnt in groups}
        for rec in self:
            rec.exam_session_count = counts.get(rec.id, 0)

    def action_view_exam_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Sessions — %s') % self.name,
            'res_model': 'edu.exam.session',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {
                'default_batch_id': self.id,
                'default_program_id': self.program_id.id,
                'default_academic_year_id': self.academic_year_id.id,
            },
        }
