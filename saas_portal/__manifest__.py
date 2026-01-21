{
    'name': 'SaaS Portal',
    'version': '19.0.1.0.0',
    'category': 'Website/Portal',
    'summary': 'Portal unificado para clientes SaaS',
    'description': """
        Portal unificado para clientes con todas sus suscripciones y servicios:
        - Vista de suscripciones activas
        - Acceso a instancias Odoo
        - Historial de citas y proyectos
        - Métricas de uso
        - Facturas y pagos
    """,
    'author': 'AutomateAI',
    'website': 'https://automateai.com.mx',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'portal',
        'website',
        'sale_subscription',
        'project',
        'appointment',
        'account',
        'saas_services',
        'k8s_saas',
        # n8n_sales is optional - dashboard adapts if not installed
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
        'views/portal_subscription_templates.xml',
        'views/portal_instance_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
