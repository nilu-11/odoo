from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('edu_timetable', 'post_install', '-at_install')
class TestSlotConflictConstraint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Template = cls.env['edu.timetable.template']
        Period = cls.env['edu.timetable.period']
        Room = cls.env['edu.room']
        Employee = cls.env['hr.employee']
        cls.Slot = cls.env['edu.timetable.slot']

        # edu.academic.year requires name, code, date_start, date_end
        cls.year = cls.env['edu.academic.year'].create({
            'name': 'Conflict Test AY',
            'code': 'CTAY26',
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 12, 31),
        })

        # edu.department required by edu.program
        cls.department = cls.env['edu.department'].create({
            'name': 'Conflict Test Dept',
            'code': 'CTDEPT',
        })

        # edu.program requires department_id, program_type, duration_*, term_system
        cls.program = cls.env['edu.program'].create({
            'name': 'Conflict Test BCS',
            'code': 'CTBCS',
            'department_id': cls.department.id,
            'duration_value': 4,
            'duration_unit': 'years',
            'program_type': 'undergraduate',
            'term_system': 'semester',
            'total_terms': 8,
        })

        # edu.program.term: name computed — only pass program_id + progression_no
        cls.term = cls.env['edu.program.term'].create({
            'program_id': cls.program.id,
            'progression_no': 1,
        })

        # edu.batch: name/code are computed. Auto-creates section 'A'/'SEC-A'.
        cls.batch = cls.env['edu.batch'].create({
            'academic_year_id': cls.year.id,
            'program_id': cls.program.id,
        })

        # section_a = the auto-created 'A' section from batch creation
        cls.section_a = cls.batch.section_ids.filtered(lambda s: s.name == 'A')[:1]

        # section_b: create a second section in the same batch with unique name/code
        cls.section_b = cls.env['edu.section'].create({
            'name': 'B',
            'code': 'SEC-B',
            'batch_id': cls.batch.id,
        })

        cls.subject = cls.env['edu.subject'].create({
            'name': 'Conflict Math', 'code': 'CMATH',
        })
        cls.subject2 = cls.env['edu.subject'].create({
            'name': 'Conflict Physics', 'code': 'CPHY',
        })

        cls.room1 = Room.create({'name': 'CR1', 'code': 'CR1'})
        cls.room2 = Room.create({'name': 'CR2', 'code': 'CR2'})
        cls.t1 = Employee.create({'name': 'Conflict Teacher One'})
        cls.t2 = Employee.create({'name': 'Conflict Teacher Two'})

        cls.template_a = Template.create({
            'academic_year_id': cls.year.id,
            'batch_id': cls.batch.id,
            'program_term_id': cls.term.id,
            'section_id': cls.section_a.id,
            'date_start': date(2026, 2, 2),
            'date_end': date(2026, 6, 30),
        })
        cls.template_b = Template.create({
            'academic_year_id': cls.year.id,
            'batch_id': cls.batch.id,
            'program_term_id': cls.term.id,
            'section_id': cls.section_b.id,
            'date_start': date(2026, 2, 2),
            'date_end': date(2026, 6, 30),
        })
        cls.period_a = Period.create({
            'template_id': cls.template_a.id,
            'name': 'P1', 'sequence': 10, 'start_time': 8.0, 'end_time': 8.75,
        })
        cls.period_b = Period.create({
            'template_id': cls.template_b.id,
            'name': 'P1', 'sequence': 10, 'start_time': 8.0, 'end_time': 8.75,
        })

    def _make_slot(self, template, period, teacher, room, subject, day='0'):
        return self.Slot.create({
            'template_id': template.id,
            'period_id': period.id,
            'subject_id': subject.id,
            'teacher_id': teacher.id,
            'room_id': room.id,
            'day_of_week': day,
        })

    def test_teacher_double_booked_raises(self):
        self._make_slot(self.template_a, self.period_a, self.t1, self.room1, self.subject)
        with self.assertRaisesRegex(ValidationError, 'Teacher'):
            self._make_slot(self.template_b, self.period_b, self.t1, self.room2, self.subject)

    def test_room_double_booked_raises(self):
        self._make_slot(self.template_a, self.period_a, self.t1, self.room1, self.subject)
        with self.assertRaisesRegex(ValidationError, 'Room'):
            self._make_slot(self.template_b, self.period_b, self.t2, self.room1, self.subject)

    def test_section_double_booked_raises(self):
        self._make_slot(self.template_a, self.period_a, self.t1, self.room1, self.subject)
        with self.assertRaisesRegex(ValidationError, 'Section'):
            self._make_slot(self.template_a, self.period_a, self.t2, self.room2, self.subject2)

    def test_distinct_day_no_conflict(self):
        self._make_slot(self.template_a, self.period_a, self.t1, self.room1, self.subject, day='0')
        slot2 = self._make_slot(self.template_b, self.period_b, self.t1, self.room1, self.subject2, day='1')
        self.assertTrue(slot2.id)
