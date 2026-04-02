import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EduBatch(models.Model):
    """Extend edu.batch with classroom counts and classroom-related actions."""

    _inherit = 'edu.batch'

    # ── Classroom counts ──────────────────────────────────────────────────────

    classroom_count = fields.Integer(
        string='Classrooms',
        compute='_compute_classroom_count',
        store=False,
    )

    def _compute_classroom_count(self):
        # Use sudo to bypass record rules so the count is always accurate
        data = self.env['edu.classroom'].sudo()._read_group(
            domain=[('batch_id', 'in', self.ids)],
            groupby=['batch_id'],
            aggregates=['__count'],
        )
        mapped = {batch.id: count for batch, count in data}
        for rec in self:
            rec.classroom_count = mapped.get(rec.id, 0)

    # ── Smart button actions ──────────────────────────────────────────────────

    def action_view_classrooms(self):
        """Open classroom list filtered to this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Classrooms — %s') % self.name,
            'res_model': 'edu.classroom',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
        }

    def action_generate_classrooms_wizard(self):
        """Generate classrooms for all sections and the current program term."""
        self.ensure_one()

        term = self.current_program_term_id
        if not term:
            raise UserError(_(
                'Batch "%s" has no Current Progression set.\n'
                'Set "Current Progression" on the batch before generating classrooms.'
            ) % self.name)

        if not self.section_ids:
            raise UserError(_(
                'Batch "%s" has no sections.\n'
                'Create sections in the Sections tab first.'
            ) % self.name)

        curriculum_lines = term.curriculum_line_ids
        if not curriculum_lines:
            raise UserError(_(
                'Program term "%s" has no subjects (curriculum lines).\n\n'
                'Navigate to: Programs → %s → Program Terms → %s → Curriculum tab '
                'and add subjects before generating classrooms.'
            ) % (term.name, self.program_id.name, term.name))

        _logger.info(
            'Generating classrooms for batch=%s term=%s sections=%s lines=%s',
            self.name, term.name,
            [s.name for s in self.section_ids],
            [l.subject_id.name for l in curriculum_lines],
        )

        # Use sudo for the existence check and create so that record rules on
        # edu.classroom (teacher-scoped) do not interfere with generation.
        Classroom = self.env['edu.classroom'].sudo()
        created_ids = []
        skipped = 0

        for section in self.section_ids:
            for line in curriculum_lines:
                existing = Classroom.search([
                    ('section_id', '=', section.id),
                    ('curriculum_line_id', '=', line.id),
                ], limit=1)
                if existing:
                    skipped += 1
                    continue
                classroom = Classroom.create({
                    'batch_id': self.id,
                    'section_id': section.id,
                    'program_term_id': term.id,
                    'curriculum_line_id': line.id,
                })
                created_ids.append(classroom.id)
                _logger.info(
                    'Created classroom id=%s: %s / %s / %s',
                    classroom.id, section.name,
                    line.subject_id.name, term.name,
                )

        _logger.info(
            'Classroom generation done: created=%d skipped=%d',
            len(created_ids), skipped,
        )

        if not created_ids:
            raise UserError(_(
                'All classrooms for "%s" / "%s" already exist (%d skipped).\n'
                'Click the Classrooms smart button to view them.'
            ) % (self.name, term.name, skipped))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Classrooms — %s') % self.name,
            'res_model': 'edu.classroom',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {
                'default_batch_id': self.id,
                'search_default_group_section': 1,
            },
            'target': 'current',
        }
