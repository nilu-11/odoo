{
    'name': 'Education: Academic Progression',
    'version': '19.0.1.0.0',
    'summary': (
        'Student academic progression history and controlled batch promotion. '
        'Foundation layer for attendance, exams, and all future academic modules.'
    ),
    'description': """
Education: Academic Progression
================================

Provides the progression history and batch promotion layer for the EMIS.

Key features:
- edu.student.progression.history — one record per student per semester/term,
  preserving exact academic placement with full audit trail
- Auto-creation of the initial progression history when a student is enrolled
- Batch Promotion Wizard — controlled, auditable transition of an entire batch
  from one progression/semester to the next
- Frozen-field protection on closed progression records
- Helper methods (_get_active_progression_history, _get_active_student_progressions)
  ready for future attendance, exam, timetable, and assignment modules
- Clean integration with existing enrollment and student flow
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'edu_academic_structure',
        'edu_enrollment',
        'edu_student',
    ],
    'data': [
        'security/edu_academic_progression_security.xml',
        'security/ir.model.access.csv',
        'views/edu_student_progression_history_views.xml',
        'views/edu_batch_promotion_wizard_views.xml',
        'views/edu_student_views.xml',
        'views/edu_batch_views.xml',
        'views/edu_academic_progression_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
