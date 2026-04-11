{
    'name': 'Education: Academic Structure',
    'version': '19.0.2.0.0',
    'summary': 'Academic structure for school/college EMIS — years, terms, departments, programs, program terms, batches, sections, subjects, and curriculum.',
    'description': """
        Education Management Information System — Academic Structure.
        Provides the foundational academic hierarchy:
        Academic Year → Term(s) [flexible]
        Department → Program → Program Term (progression mapping) → Curriculum Line
        Program → Batch → Section
    """,
    'author': 'Innovax Solutions',
    'category': 'Education',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/edu_academic_year_views.xml',
        'views/edu_term_views.xml',
        'views/edu_department_views.xml',
        'views/edu_program_views.xml',
        'views/edu_program_term_views.xml',
        'views/edu_batch_views.xml',
        'views/edu_section_views.xml',
        'views/edu_subject_views.xml',
        'views/edu_curriculum_line_views.xml',
        'views/menu_views.xml',
        # 'data/demo_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
