from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DAYS_OF_WEEK = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class EduTimetableSlot(models.Model):
    """A single scheduled slot in a timetable template.

    A slot represents both a recurring rule (day_of_week + period_id,
    applying across template.date_start..date_end) and a concrete
    occurrence via computed ``start_datetime`` / ``end_datetime``
    (projected to the first in-range matching weekday). This dual
    nature lets Odoo's gantt and calendar views bind natively without
    requiring a materialized-occurrences table.

    Conflict detection (teacher/room/section double-booking) is
    enforced by a Python constraint that runs on create and write.
    """

    _name = 'edu.timetable.slot'
    _description = 'Timetable Slot'
    _inherit = ['mail.thread']
    _order = 'template_id, day_of_week, period_id'
    _rec_name = 'name'

    # ── Relations ─────────────────────────────────────────────────────────
    template_id = fields.Many2one(
        comodel_name='edu.timetable.template',
        string='Template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    period_id = fields.Many2one(
        comodel_name='edu.timetable.period',
        string='Period',
        required=True,
        ondelete='restrict',
        domain="[('template_id', '=', template_id)]",
    )
    classroom_id = fields.Many2one(
        comodel_name='edu.classroom',
        string='Classroom',
        ondelete='restrict',
        help='Links the slot to an edu.classroom (section × subject hub).',
    )

    # ── Denormalised from classroom / template for gantt grouping ─────────
    subject_id = fields.Many2one(
        comodel_name='edu.subject',
        string='Subject',
        required=True,
        ondelete='restrict',
    )
    teacher_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Teacher',
        required=True,
        ondelete='restrict',
        index=True,
    )
    room_id = fields.Many2one(
        comodel_name='edu.room',
        string='Room',
        required=True,
        ondelete='restrict',
        index=True,
    )
    section_id = fields.Many2one(
        comodel_name='edu.section',
        related='template_id.section_id',
        store=True,
        index=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='edu.academic.year',
        related='template_id.academic_year_id',
        store=True,
    )

    # ── Recurrence rule ──────────────────────────────────────────────────
    day_of_week = fields.Selection(
        selection=DAYS_OF_WEEK,
        string='Day of Week',
        required=True,
        index=True,
    )

    # ── Slot classification ──────────────────────────────────────────────
    slot_type = fields.Selection(
        selection=[
            ('regular', 'Regular Class'),
            ('exam', 'Exam'),
            ('event', 'Event'),
            ('cancelled', 'Cancelled'),
        ],
        string='Type',
        default='regular',
        required=True,
    )

    # ── Computed datetime (for gantt/calendar view binding) ──────────────
    start_datetime = fields.Datetime(
        string='Start',
        compute='_compute_datetimes',
        store=True,
        index=True,
    )
    end_datetime = fields.Datetime(
        string='End',
        compute='_compute_datetimes',
        store=True,
        index=True,
    )

    # ── Display / name ───────────────────────────────────────────────────
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )

    # ── Depended template fields (cached) ────────────────────────────────
    template_date_start = fields.Date(
        related='template_id.date_start',
        store=True,
    )
    template_date_end = fields.Date(
        related='template_id.date_end',
        store=True,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('subject_id', 'day_of_week', 'period_id')
    def _compute_name(self):
        day_map = dict(DAYS_OF_WEEK)
        for rec in self:
            day_label = day_map.get(rec.day_of_week, '')
            subject = rec.subject_id.display_name or ''
            period = rec.period_id.name or ''
            rec.name = _('%s — %s @ %s') % (day_label, subject, period) if subject else ''

    @api.depends(
        'day_of_week',
        'period_id.start_time',
        'period_id.end_time',
        'template_date_start',
    )
    def _compute_datetimes(self):
        """Project the first occurrence of (day_of_week × period) inside
        the template's date range. Both start_datetime and end_datetime
        are naive UTC datetimes — Odoo handles user-TZ conversion in views.
        """
        for rec in self:
            if not (rec.day_of_week and rec.period_id and rec.template_date_start):
                rec.start_datetime = False
                rec.end_datetime = False
                continue
            start_date = rec.template_date_start
            target_weekday = int(rec.day_of_week)
            # Python weekday(): Mon=0..Sun=6 — matches our DAYS_OF_WEEK
            days_ahead = (target_weekday - start_date.weekday()) % 7
            first_date = start_date + timedelta(days=days_ahead)
            start_hour = int(rec.period_id.start_time)
            start_min = int(round((rec.period_id.start_time - start_hour) * 60))
            end_hour = int(rec.period_id.end_time)
            end_min = int(round((rec.period_id.end_time - end_hour) * 60))
            rec.start_datetime = datetime(
                first_date.year, first_date.month, first_date.day,
                start_hour, start_min, 0,
            )
            rec.end_datetime = datetime(
                first_date.year, first_date.month, first_date.day,
                end_hour, end_min, 0,
            )

    # ── Conflict detection constraint ────────────────────────────────────
    @api.constrains(
        'day_of_week',
        'period_id',
        'teacher_id',
        'room_id',
        'section_id',
        'template_date_start',
        'template_date_end',
        'slot_type',
    )
    def _check_no_conflicts(self):
        """Prevent double-booking of teachers, rooms, and sections.

        Two slots conflict if they share the same day_of_week, their periods
        have overlapping time ranges, and their template date ranges overlap,
        AND they share at least one of: teacher_id, room_id, section_id.

        Cancelled slots are excluded from conflict checks.
        """
        for rec in self:
            if rec.slot_type == 'cancelled':
                continue
            if not (rec.period_id and rec.day_of_week):
                continue
            candidates = self.search([
                ('id', '!=', rec.id),
                ('day_of_week', '=', rec.day_of_week),
                ('slot_type', '!=', 'cancelled'),
                ('template_date_start', '<=', rec.template_date_end),
                ('template_date_end', '>=', rec.template_date_start),
            ])
            for other in candidates:
                if not (
                    rec.period_id.start_time < other.period_id.end_time
                    and other.period_id.start_time < rec.period_id.end_time
                ):
                    continue
                if rec.teacher_id == other.teacher_id:
                    raise ValidationError(_(
                        'Teacher conflict: %(teacher)s is already booked in '
                        'slot "%(other)s" during this time.'
                    ) % {
                        'teacher': rec.teacher_id.display_name,
                        'other': other.display_name,
                    })
                if rec.room_id == other.room_id:
                    raise ValidationError(_(
                        'Room conflict: %(room)s is already booked in '
                        'slot "%(other)s" during this time.'
                    ) % {
                        'room': rec.room_id.display_name,
                        'other': other.display_name,
                    })
                if rec.section_id == other.section_id:
                    raise ValidationError(_(
                        'Section conflict: %(section)s is already scheduled in '
                        'slot "%(other)s" during this time.'
                    ) % {
                        'section': rec.section_id.display_name,
                        'other': other.display_name,
                    })

    @api.model_create_multi
    def create(self, vals_list):
        slots = super().create(vals_list)
        # If a slot was created from an exam session "Schedule" button, link back.
        # (Phase 3 will add timetable_slot_id field to edu.exam.session.)
        exam_session_id = self.env.context.get('exam_session_id_for_link')
        if exam_session_id and len(slots) == 1:
            ExamSession = self.env.get('edu.exam.session')
            if ExamSession is not None:
                session = ExamSession.browse(exam_session_id)
                if session.exists() and 'timetable_slot_id' in session._fields:
                    session.write({
                        'timetable_slot_id': slots.id,
                        'room_id': slots.room_id.id,
                    })
        return slots
