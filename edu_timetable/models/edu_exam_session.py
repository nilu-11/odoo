from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EduExamSession(models.Model):
    _inherit = 'edu.exam.session'

    timetable_slot_id = fields.Many2one(
        comodel_name='edu.timetable.slot',
        string='Timetable Slot',
        ondelete='set null',
        help='The timetable slot this exam occupies (if scheduled on a timetable).',
    )
    room_id = fields.Many2one(
        comodel_name='edu.room',
        string='Exam Room',
        ondelete='set null',
    )

    def action_schedule_on_timetable(self):
        """Open a slot form pre-populated with exam defaults. The created
        slot will back-link to this exam session via
        edu.timetable.slot.create() which reads the 'exam_session_id_for_link'
        context.
        """
        self.ensure_one()
        if self.timetable_slot_id:
            raise UserError(_(
                'This exam session is already scheduled on timetable slot "%s". '
                'Remove the slot first to reschedule.'
            ) % self.timetable_slot_id.display_name)

        default_subject = False
        if 'subject_id' in self._fields and self.subject_id:
            default_subject = self.subject_id.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Exam on Timetable'),
            'res_model': 'edu.timetable.slot',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_slot_type': 'exam',
                'default_subject_id': default_subject,
                'default_room_id': self.room_id.id if self.room_id else False,
                'exam_session_id_for_link': self.id,
            },
        }
