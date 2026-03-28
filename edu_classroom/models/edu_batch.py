from odoo import api, fields, models, _


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
        Classroom = self.env['edu.classroom']
        data = Classroom._read_group(
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
        """Generate classrooms for all sections and the current program term.

        Iterates every section in this batch and every curriculum line in the
        batch's current_program_term_id, creating classrooms where they do not
        yet exist.  Returns a client notification action summarising the result.
        """
        self.ensure_one()
        if not self.current_program_term_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Program Term'),
                    'message': _(
                        'Please set a Current Progression on the batch '
                        'before generating classrooms.'
                    ),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        Classroom = self.env['edu.classroom']
        created_total = self.env['edu.classroom']
        for section in self.section_ids:
            created = Classroom._generate_classrooms_for_section(
                section, self.current_program_term_id
            )
            created_total |= created
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Classrooms Generated'),
                'message': _(
                    '%d classroom(s) created for batch "%s".'
                ) % (len(created_total), self.name),
                'type': 'success',
                'sticky': False,
            },
        }
