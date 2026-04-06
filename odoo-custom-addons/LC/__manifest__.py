{
    'name': 'Letter of Credit Management',
    'summary': 'Manage Letters of Credit',
    'version': '19.0.1.0',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/letter_of_credit_sequence.xml',
        'views/letter_of_credit_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}