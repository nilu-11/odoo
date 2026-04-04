import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class EduClassroom(models.Model):
    """Extend edu.classroom with continuous assessment integration."""

    _inherit = 'edu.classroom'

    assessment_record_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_record_count',
        store=False,
    )
    assessment_pending_count = fields.Integer(
        string='Pending Assessments',
        compute='_compute_assessment_record_count',
        store=False,
        help='Assessment records still in draft or confirmed state.',
    )

    def _compute_assessment_record_count(self):
        AssessmentRecord = self.env['edu.continuous.assessment.record']
        all_groups = AssessmentRecord._read_group(
            domain=[('classroom_id', 'in', self.ids)],
            groupby=['classroom_id'],
            aggregates=['__count'],
        )
        all_counts = {cl.id: cnt for cl, cnt in all_groups}
        pending_groups = AssessmentRecord._read_group(
            domain=[('classroom_id', 'in', self.ids), ('state', 'in', ('draft', 'confirmed'))],
            groupby=['classroom_id'],
            aggregates=['__count'],
        )
        pending_counts = {cl.id: cnt for cl, cnt in pending_groups}
        for rec in self:
            rec.assessment_record_count = all_counts.get(rec.id, 0)
            rec.assessment_pending_count = pending_counts.get(rec.id, 0)

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

    def action_new_assessment(self):
        """Open the bulk generate wizard pre-filled for this classroom."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Assessment — %s') % self.name,
            'res_model': 'edu.assessment.bulk.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_classroom_id': self.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }

    def action_pending_assessments(self):
        """Open pending (draft/confirmed) assessment records for this classroom."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pending Assessments — %s') % self.name,
            'res_model': 'edu.continuous.assessment.record',
            'view_mode': 'list,form',
            'domain': [
                ('classroom_id', '=', self.id),
                ('state', 'in', ('draft', 'confirmed')),
            ],
            'context': {
                'default_classroom_id': self.id,
                'default_section_id': self.section_id.id,
                'default_subject_id': self.subject_id.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }
