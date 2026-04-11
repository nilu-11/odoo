{
    'name': 'Education: Timetable',
    'version': '19.0.1.0.0',
    'summary': 'Weekly class schedules with conflict detection, gantt/calendar views, and exam scheduling integration.',
    'description': """
Education Timetable
===================

Provides weekly recurring class schedules scoped to (academic year × section × program term).
Core entities:

- edu.room — physical room master
- edu.timetable.template — one weekly schedule per cohort
- edu.timetable.period — time slots within a template (Period 1 = 08:00-08:45, etc.)
- edu.timetable.slot — a single cell (day × period × subject × teacher × room)

Features:

- Hard conflict detection (teacher / room / section can't double-book)
- Native Odoo gantt view grouped by teacher or room
- Calendar view (week default) color-coded by subject
- Soft integration with edu_exam — exam sessions can occupy timetable slots
- Portal "My Schedule" sidebar item for teachers and students
""",
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'web_gantt',
        'edu_academic_structure',
        'edu_classroom',
        'edu_hr',
        'edu_exam',
        'edu_portal',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/edu_room_views.xml',
        'views/edu_timetable_period_views.xml',
        'views/edu_timetable_template_views.xml',
        'views/edu_timetable_slot_views.xml',
        'views/edu_exam_session_views.xml',
        'views/portal_schedule_templates.xml',
        'views/menu_views.xml',
        'data/portal_sidebar_data.xml',
    ],
    'demo': [
        'data/edu_room_demo.xml',
        'data/edu_timetable_demo.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
