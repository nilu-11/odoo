{
    'name': 'EMIS Portal — Kopilā',
    'version': '19.0.2.0.0',
    'category': 'Education',
    'summary': 'Interactive teacher/student/parent portal with Kopilā design system',
    'description': """
        Custom EMIS portal for teachers, students, and parents.
        Google Classroom-style hub with attendance, marking, gradebook,
        messaging, announcements, and more.
        Built with the Kopilā design system.
    """,
    'author': 'Innovax Solutions',
    'depends': [
        'base',
        'mail',
        'portal',
        'edu_classroom',
        'edu_attendance',
        'edu_exam',
        'edu_assessment',
        'edu_result',
        'edu_fees',
        'edu_hr',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/edu_student_views.xml',
        'views/edu_guardian_views.xml',
        'views/hr_employee_views.xml',
        'views/edu_classroom_post_views.xml',
        'views/portal_layout.xml',
        'views/teacher_templates.xml',
        'views/teacher_classroom_templates.xml',
        'views/student_templates.xml',
        'views/student_classroom_templates.xml',
        'views/parent_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'edu_portal/static/src/css/portal.css',
            'edu_portal/static/src/js/portal.js',
            'edu_portal/static/src/js/entry.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
