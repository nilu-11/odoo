{
    'name': 'My Project Manager',
    'version': '19.0.1.0.1',
    'summary': 'Simple project and task tracker',
    'author': 'Your Name',
    'category': 'Project',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_views.xml',
        'views/task_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}