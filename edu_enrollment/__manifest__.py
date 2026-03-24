{
    'name': 'Education: Enrollment',
    'version': '19.0.1.0.0',
    'summary': (
        'Official enrollment — converts accepted admission applications '
        'into institutional enrollment records with academic placement '
        'and financial context preservation.'
    ),
    'description': """
        Education Management Information System — Enrollment Module.

        Bridges formal admission and the future student lifecycle:

        1. Enrollment Record — official institutional onboarding record
        2. Enrollment Readiness — validates admission prerequisites
        3. Academic Placement — confirms program/batch/term placement
        4. Financial Snapshot — preserves fee, payment plan, and
           scholarship outcome from admission
        5. Checklist — lightweight document / requirement verification
        6. Student Handoff — future module integration hook

        Integrates with:
        - edu_admission (applications, scholarship reviews)
        - edu_pre_admission_crm (applicant profiles, guardians)
        - edu_fees_structure (fee structures, payment plans)
        - edu_academic_structure (programs, batches, academic years,
          program terms)
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'edu_admission',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/edu_enrollment_views.xml',
        'views/edu_enrollment_checklist_views.xml',
        'views/edu_admission_application_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
