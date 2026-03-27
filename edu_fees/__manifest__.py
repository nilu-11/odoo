{
    'name': 'Education: Student Finance',
    'version': '19.0.1.0.0',
    'summary': (
        'Student-level fee planning, due generation, payment tracking, '
        'and enrollment fee blocking for the EMIS.'
    ),
    'description': """
Education Student Finance — Stage 1
====================================

Extends the existing fee configuration architecture with student-level
billing and payment tracking:

1. **Fee Head Enhancements** — fee_nature (normal / deposit / fine /
   optional), is_required_for_enrollment flag, allow_adjustment flag.
2. **Schedule Templates** — configurable due-date schedules (full
   payment or installment-based with percentage splits and offset days).
3. **Student Fee Plan** — per-enrollment fee plan generated from the
   fee structure, with scholarship discount distribution.
4. **Student Fee Dues** — individual payable records generated from
   plan lines via schedule templates.
5. **Student Payments** — internal EMIS-level payment recording with
   multi-due allocation support.
6. **Enrollment Fee Blocking** — configurable gate that prevents
   enrollment confirmation until all required-for-enrollment fees are
   paid, with auditable manager override.
7. **Finance Dashboard** — summary fields and smart buttons on both
   the enrollment and student forms.

Integrates with:
- edu_fees_structure (fee heads, fee structures, payment plans)
- edu_admission (scholarship reviews, applications)
- edu_enrollment (enrollment readiness, blocking)
- edu_student (finance summary, smart buttons)
- edu_academic_structure (programs, batches, program terms)
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'edu_student',
        'edu_fees_structure',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/edu_fee_head_views.xml',
        'views/edu_schedule_template_views.xml',
        'views/edu_student_fee_plan_views.xml',
        'views/edu_student_fee_due_views.xml',
        'views/edu_student_payment_views.xml',
        'views/edu_enrollment_views.xml',
        'views/edu_student_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
