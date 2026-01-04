{
    'name': 'Kubernetes SaaS',
    'version': '19.0.1.0.0',
    'category': 'Technical/SaaS',
    'summary': 'Gestión de instancias Odoo en Kubernetes',
    'description': """
        Módulo para gestionar instancias Odoo desplegadas en Kubernetes:
        - Crear/eliminar deployments automáticamente
        - Gestión de bases de datos
        - Monitoreo de recursos
        - Configuración de Cloudflare tunnels
        - Integración con sale_subscription
    """,
    'author': 'AutomateAI',
    'website': 'https://automateai.com.mx',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'sale_subscription',
        'saas_services',
    ],
    'data': [
        'security/k8s_saas_security.xml',
        'security/ir.model.access.csv',
        'data/k8s_config_data.xml',
        'views/k8s_cluster_views.xml',
        'views/k8s_instance_views.xml',
        'views/k8s_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['kubernetes', 'paramiko'],
    },
}
