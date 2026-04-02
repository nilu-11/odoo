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
        from odoo.exceptions import UserError
        self.ensure_one()

        if not self.current_program_term_id:
            raise UserError(_(
                'Batch "%s" has no Current Progression set.\n'
                'Go to the batch form and set "Current Progression" before '
                'generating classrooms.'
            ) % self.name)

        if not self.section_ids:
            raise UserError(_(
                'Batch "%s" has no sections.\n'
                'Create at least one section in the Sections tab before '
                'generating classrooms.'
            ) % self.name)

        term = self.current_program_term_id
        if not term.curriculum_line_ids:
            raise UserError(_(
                'Program term "%s" has no curriculum lines (subjects) configured.\n\n'
                'Go to: Academic Structure → Programs → open the program → '
                'Program Terms tab → open "%s" → add subjects in the '
                'Curriculum tab.\n\n'
                'Classrooms are created one per subject per section, so at '
                'least one subject must be configured.'
            ) % (term.name, term.name))

        Classroom = self.env['edu.classroom']
        created_total = self.env['edu.classroom']
        skipped = 0
        for section in self.section_ids:
            created = Classroom._generate_classrooms_for_section(section, term)
            created_total |= created
            skipped += len(term.curriculum_line_ids) - len(created)

        if not created_total:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Already Up To Date'),
                    'message': _(
                        'All %d classroom(s) for batch "%s" / term "%s" '
                        'already exist — nothing new to create.'
                    ) % (skipped, self.name, term.name),
                    'type': 'info',
                    'sticky': False,
                },
            }

        msg = _('%d classroom(s) created for batch "%s" / term "%s".') % (
            len(created_total), self.name, term.name,
        )
        if skipped:
            msg += _(' %d already existed and were skipped.') % skipped

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Classrooms Generated'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }
