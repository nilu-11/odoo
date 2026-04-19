{
    'name': 'Education: Pre-Admission CRM',
    'version': '19.0.3.0.0',
    'summary': (
        'Pre-admission pipeline — inquiries, counseling, applicant profiles, '
        'guardians, academic history, and CRM-driven conversion to admission applications.'
    ),
    'description': """
        Education Management Information System — Pre-Admission CRM.

        Extends Odoo CRM as the pipeline engine for the full pre-admission workflow:
          • Inquiry intake and prospect qualification
          • Structured applicant profile (res.partner as identity base)
          • Guardian registry with relational applicant–guardian links
          • Academic history per applicant
          • Counseling and follow-up tracking
          • Conversion trigger to edu.admission.application (requires edu_admission)

        Design principles:
          • CRM = workflow layer only; master data lives in structured EMIS models
          • res.partner = universal identity base for applicants and guardians
          • Designed for future student lifecycle, portal access, and sibling relations
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'mail',
        'contacts',
        'hr',
        'edu_academic_structure',
    ],
    # edu_admission is an optional downstream dependency.
    # When installed, it provides edu.admission.register and edu.admission.application.
    # The conversion action (action_convert_to_admission_application) checks at runtime.
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/edu_relationship_type_data.xml',
        'data/edu_activity_type_data.xml',
        'data/edu_qualification_data.xml',
        'views/edu_relationship_type_views.xml',
        'views/edu_applicant_profile_views.xml',
        'views/edu_guardian_views.xml',
        'views/hr_employee_views.xml',
        'views/crm_lead_views.xml',
        'views/edu_interaction_log_views.xml',
        'views/menu_views.xml',
        'views/edu_qualification_views.xml',
        'wizard/edu_lead_merge_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edu_pre_admission_crm/static/src/js/activity_reload.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
