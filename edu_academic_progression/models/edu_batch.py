from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EduBatch(models.Model):
    _inherit = 'edu.batch'

    # ── Progression Counts ────────────────────────────────────────────────────

    progression_history_count = fields.Integer(
        compute='_compute_progression_counts',
        string='Progression Records',
    )
    active_progression_count = fields.Integer(
        compute='_compute_progression_counts',
        string='Active Progressions',
    )

    def _compute_progression_counts(self):
        ProgressionHistory = self.env['edu.student.progression.history']
        for batch in self:
            batch.progression_history_count = ProgressionHistory.search_count([
                ('batch_id', '=', batch.id),
            ])
            batch.active_progression_count = ProgressionHistory.search_count([
                ('batch_id', '=', batch.id),
                ('state', '=', 'active'),
            ])

    # ── Helpers for downstream modules ────────────────────────────────────────

    def _get_active_student_progressions(self):
        """Return all active progression history records for this batch.

        Call from attendance, timetable, classroom allocation, and similar
        modules to enumerate the current academic context for all enrolled
        students in this batch cohort.
        """
        self.ensure_one()
        return self.env['edu.student.progression.history'].search([
            ('batch_id', '=', self.id),
            ('state', '=', 'active'),
        ])

    # ── Smart Button Actions ──────────────────────────────────────────────────

    def action_view_progression_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progression History — %s') % self.name,
            'res_model': 'edu.student.progression.history',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
        }

    def action_open_promotion_wizard(self):
        """Open the Batch Promotion Wizard for this batch."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_('Only active batches can be promoted.'))
        if not self.current_program_term_id:
            raise UserError(_(
                'Batch "%s" has no current progression configured. '
                'Set "Current Progression" on the batch before running a promotion.'
            ) % self.name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Promote Batch — %s') % self.name,
            'res_model': 'edu.batch.promotion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_id': self.id},
        }
