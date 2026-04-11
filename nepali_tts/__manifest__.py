{
    'name': 'Nepali Text to Speech',
    'version': '19.0.1.0.0',
    'summary': 'Type Nepali text and play it as audio inside Odoo.',
    'author': 'Innovax Solutions',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'views/nepali_tts_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'nepali_tts/static/src/xml/tts_widget.xml',
            'nepali_tts/static/src/js/tts_widget.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
