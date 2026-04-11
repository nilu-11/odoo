from odoo import fields, models


class EduRoom(models.Model):
    """Physical room master — classrooms, labs, halls, offices.

    Rooms are referenced by timetable slots (for regular classes) and by
    exam sessions (when an exam is scheduled onto the timetable). A room's
    capacity is advisory only — no hard constraint blocks over-capacity
    scheduling at this stage.
    """

    _name = 'edu.room'
    _description = 'Physical Room'
    _order = 'building, floor, code, name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    capacity = fields.Integer(string='Capacity', default=0)
    building = fields.Char(string='Building')
    floor = fields.Char(string='Floor')
    room_type = fields.Selection(
        selection=[
            ('classroom', 'Classroom'),
            ('lab', 'Laboratory'),
            ('hall', 'Hall / Auditorium'),
            ('office', 'Office'),
            ('other', 'Other'),
        ],
        string='Type',
        default='classroom',
        required=True,
    )
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('edu_room_code_unique', 'unique(code)', 'Room code must be unique.'),
    ]
