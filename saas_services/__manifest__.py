{
    'name': 'SaaS Services Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales/Services',
    'summary': 'Integración de servicios con citas y proyectos automáticos',
    'description': """
        Módulo que integra:
        - Venta de servicios (horas, proyectos, soporte)
        - Creación automática de proyectos al vender
        - Agendamiento de citas según disponibilidad
        - Notificaciones automáticas al cliente
    """,
    'author': 'AutomateAI',
    'website': 'https://automateai.com.mx',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'sale_project',
        'sale_subscription',
        'appointment',
        'hr_timesheet',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/saas_services_security.xml',
        'data/appointment_types.xml',
        'data/mail_templates.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/saas_services_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
