from datetime import date, datetime

from odoo.tests.common import TransactionCase, tagged


@tagged('edu_timetable', 'post_install', '-at_install')
class TestSlotDatetimeCompute(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['edu.timetable.template']
        cls.Period = cls.env['edu.timetable.period']
        cls.Slot = cls.env['edu.timetable.slot']
        cls.Room = cls.env['edu.room']
        cls.Employee = cls.env['hr.employee']

        # Build fixtures inline — avoids brittleness around demo xml_ids.

        # edu.academic.year requires name, code, date_start, date_end.
        # Use a far-future year (2099) to avoid _check_no_overlap collision
        # with pre-existing demo academic years in the test DB.
        cls.year = cls.env['edu.academic.year'].create({
            'name': 'Test AY 2099',
            'code': 'TAY2099',
            'date_start': date(2099, 1, 1),
            'date_end': date(2099, 12, 31),
        })

        # edu.department is required by edu.program
        cls.department = cls.env['edu.department'].create({
            'name': 'Test Department DT',
            'code': 'TDTDT',
        })

        # edu.program requires name, code, department_id, program_type,
        # duration_value, duration_unit, total_terms, term_system
        cls.program = cls.env['edu.program'].create({
            'name': 'Test BCS DT',
            'code': 'TBCSDT',
            'department_id': cls.department.id,
            'duration_value': 4,
            'duration_unit': 'years',
            'program_type': 'undergraduate',
            'term_system': 'semester',
            'total_terms': 8,
        })

        # edu.program.term: name and code are computed — only pass program_id
        # and progression_no. total_terms=8 so progression_no=1 is valid.
        cls.term = cls.env['edu.program.term'].create({
            'program_id': cls.program.id,
            'progression_no': 1,
        })

        # edu.batch: name and code are computed from program + academic_year.
        # Do NOT pass name/code. Batch auto-creates section 'A' / 'SEC-A'.
        cls.batch = cls.env['edu.batch'].create({
            'academic_year_id': cls.year.id,
            'program_id': cls.program.id,
        })

        # The auto-created section ('A') is what we use for the template.
        cls.section = cls.batch.section_ids[0]

        cls.subject = cls.env['edu.subject'].create({
            'name': 'Test Math DT',
            'code': 'TMATHDT',
        })
        cls.room = cls.Room.create({
            'name': 'Test Room DT1',
            'code': 'TRDT1',
            'room_type': 'classroom',
        })
        cls.teacher = cls.Employee.create({
            'name': 'Test Teacher DT One',
        })

        # Template starts on Mon 2099-01-05 (Jan 5 2099 is a Monday)
        cls.template = cls.Template.create({
            'academic_year_id': cls.year.id,
            'batch_id': cls.batch.id,
            'program_term_id': cls.term.id,
            'section_id': cls.section.id,
            'date_start': date(2099, 1, 5),
            'date_end': date(2099, 6, 30),
        })
        cls.period = cls.Period.create({
            'template_id': cls.template.id,
            'name': 'Period 1',
            'sequence': 10,
            'start_time': 8.0,
            'end_time': 8.75,   # 08:00–08:45
        })

    def test_slot_on_monday_aligns_with_template_start(self):
        """A Monday slot whose template starts Mon 2099-01-05 → datetimes on that exact day."""
        slot = self.Slot.create({
            'template_id': self.template.id,
            'period_id': self.period.id,
            'subject_id': self.subject.id,
            'teacher_id': self.teacher.id,
            'room_id': self.room.id,
            'day_of_week': '0',  # Monday
        })
        self.assertEqual(slot.start_datetime, datetime(2099, 1, 5, 8, 0, 0))
        self.assertEqual(slot.end_datetime, datetime(2099, 1, 5, 8, 45, 0))

    def test_slot_on_wednesday_projects_forward(self):
        """A Wednesday slot from a Monday-starting template → datetimes on 2099-01-07."""
        slot = self.Slot.create({
            'template_id': self.template.id,
            'period_id': self.period.id,
            'subject_id': self.subject.id,
            'teacher_id': self.teacher.id,
            'room_id': self.room.id,
            'day_of_week': '2',  # Wednesday
        })
        self.assertEqual(slot.start_datetime, datetime(2099, 1, 7, 8, 0, 0))
        self.assertEqual(slot.end_datetime, datetime(2099, 1, 7, 8, 45, 0))
