{
    'name' : 'Hospital Management System',
    'author' : 'Nilima Shrestha',
    'version' : '19.0.1.0',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application':True,
    'sequence': 1,
    'depends' : [
        'mail',
        'sale',
    ],
    'data' : [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/patient_views.xml",
        "views/patient_view_readonly.xml",
        "views/appointment_views.xml",
        "views/patient_tags_views.xml",
        "views/menu.xml",
    ]
}