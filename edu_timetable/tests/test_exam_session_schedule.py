from odoo.tests.common import TransactionCase, tagged


@tagged('edu_timetable', 'post_install', '-at_install')
class TestExamSessionSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Room = cls.env['edu.room']
        cls.ExamSession = cls.env['edu.exam.session']
        cls.room = cls.Room.create({
            'name': 'Exam Hall',
            'code': 'EHALL1',
            'room_type': 'hall',
        })

    def test_exam_session_has_timetable_slot_and_room_fields(self):
        """edu_timetable must add optional timetable_slot_id and room_id fields to exam session."""
        fields_dict = self.ExamSession._fields
        self.assertIn('timetable_slot_id', fields_dict)
        self.assertIn('room_id', fields_dict)
        self.assertEqual(fields_dict['timetable_slot_id'].comodel_name, 'edu.timetable.slot')
        self.assertEqual(fields_dict['room_id'].comodel_name, 'edu.room')

    def test_exam_session_accepts_room_assignment(self):
        """An existing exam session should accept a room assignment."""
        session = self.env['edu.exam.session'].search([], limit=1)
        if not session:
            self.skipTest('No edu.exam.session fixture available')
        session.room_id = self.room
        self.assertEqual(session.room_id, self.room)
