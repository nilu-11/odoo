{
    'name': 'Education: Student Master',
    'version': '19.0.1.0.0',
    'summary': (
        'Official student master — creates and manages the institutional '
        'student identity from enrollment, with lifecycle tracking, '
        'academic placement, and integration hooks for future modules.'
    ),
    'description': """
Education Student Master
========================

Creates the official long-term student record after enrollment.

Key features:
- Student identity linked to partner, applicant profile, and enrollment
- Auto-generated institutional student number (student_no)
- Auto-generated academic roll number from batch context
- Student lifecycle management (active → graduated / withdrawn / alumni)
- Status history audit trail
- Guardian visibility through normalized applicant profile relations
- Clean integration points for future billing, attendance, exam, and portal modules
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'edu_enrollment',
        'edu_admission',
        'edu_pre_admission_crm',
        'edu_academic_structure',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/edu_student_views.xml',
        'views/edu_student_status_history_views.xml',
        'views/edu_enrollment_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
