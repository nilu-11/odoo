from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EduTimetablePeriod(models.Model):
    """A time slot row in a timetable template.

    Period 1 = 08:00–08:45, Period 2 = 08:45–09:30, etc. Times are stored
    as Float hours (Odoo convention — float_time widget renders HH:MM).
    """

    _name = 'edu.timetable.period'
    _description = 'Timetable Period'
    _order = 'template_id, sequence, start_time'
    _rec_name = 'name'

    template_id = fields.Many2one(
        comodel_name='edu.timetable.template',
        string='Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    start_time = fields.Float(string='Start Time', required=True)
    end_time = fields.Float(string='End Time', required=True)
    is_break = fields.Boolean(string='Break', default=False)

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for rec in self:
            if rec.start_time < 0 or rec.start_time >= 24:
                raise ValidationError(_('Start time must be between 00:00 and 23:59.'))
            if rec.end_time <= rec.start_time:
                raise ValidationError(_('End time must be after start time.'))
            if rec.end_time > 24:
                raise ValidationError(_('End time cannot exceed 24:00.'))
