{
    'name': 'License Test Server',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Simula el servidor de licencias de Odoo para pruebas de seguridad',
    'description': """
        Este módulo crea un endpoint que simula services.odoo.com/publisher-warranty/
        para probar vulnerabilidades del sistema de licencias.

        SOLO PARA PRUEBAS DE SEGURIDAD - NO USAR EN PRODUCCIÓN
    """,
    'author': 'Security Testing',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/license_config_views.xml',
        'views/license_request_log_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
