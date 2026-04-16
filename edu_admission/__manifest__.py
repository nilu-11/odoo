{
    'name': 'Education: Admission',
    'version': '19.0.2.0.0',
    'summary': (
        'Formal admission lifecycle — registers, applications, '
        'scholarship review, offer letters, and enrollment handoff.'
    ),
    'description': """
        Education Management Information System — Admission Module.

        Manages the formal admission lifecycle after pre-admission (CRM-based
        prospecting and applicant profiling):

        1. Admission Register — intake configuration per program/batch/year
        2. Admission Application — the central admission record
        3. Scholarship Scheme — master scholarship catalog
        4. Scholarship Review — per-application scholarship assessment with
           stacking / capping logic
        5. Offer Letter — generation, acceptance, rejection
        6. Enrollment Handoff — future module integration hook

        Integrates with:
        - edu_pre_admission_crm (applicant profiles, guardians, CRM leads)
        - edu_fees_structure (fee structures, payment plans)
        - edu_academic_structure (programs, batches, academic years)
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'edu_academic_structure',
        'edu_pre_admission_crm',
        'edu_fees_structure',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/edu_admission_register_views.xml',
        'views/edu_scholarship_stacking_group_views.xml',
        'views/edu_scholarship_scheme_views.xml',
        'views/edu_admission_scholarship_review_views.xml',
        'views/edu_admission_application_views.xml',
        'views/menu_views.xml',
        'report/edu_admission_offer_letter_report.xml',
        'report/edu_admission_offer_letter_template.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
