{
    'name': 'Education: Fee Structure',
    'version': '19.0.1.0.0',
    'summary': 'Fee configuration for school/college EMIS — fee heads, fee terms, fee structures, and payment plans.',
    'description': """
        Education Management Information System — Fee Structure.

        Fee Head — reusable fee components (Tuition, Lab, Admission, University Reg, etc.)
        Fee Term — named payment timing labels (At Admission, Installment 1, Semester Fee, etc.)
        Fee Structure — full program fee plan per intake cohort: amounts per stage across all semesters
        Fee Structure Lines — what fee is owed per progression stage (no scheduling here)
        Fee Payment Plan — configurable HOW fees are collected:
            • Installment-Based: fee heads assigned to named installment slots
            • Monthly: fixed monthly billing over N months with configurable exclusions

        Designed for integration with:
        - Admission module (offer letters, application fees)
        - Enrollment module (student fee assignment, plan selection)
        - Billing/Accounting module (invoice generation per plan)
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'edu_academic_structure'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/edu_fee_head_views.xml',
        'views/edu_fee_term_views.xml',
        'views/edu_fee_payment_plan_views.xml',
        'views/edu_fee_structure_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
