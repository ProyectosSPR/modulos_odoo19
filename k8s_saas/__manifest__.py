{
    'name': 'Kubernetes SaaS',
    'version': '19.0.2.0.0',
    'category': 'Technical/SaaS',
    'summary': 'Gestion de instancias Odoo en Kubernetes con multi-cluster',
    'description': """
        Modulo para gestionar instancias Odoo desplegadas en Kubernetes:

        CARACTERISTICAS:
        - Soporte multi-cluster (local, Digital Ocean, AWS, etc.)
        - Templates de manifiestos YAML personalizables
        - Planes de instancia con recursos configurables
        - Creacion automatica de bases de datos PostgreSQL
        - Integracion con Cloudflare Tunnel
        - Gestion del ciclo de vida (crear, detener, reiniciar, eliminar)
        - Monitoreo de estado de pods
        - Historico de manifiestos aplicados

        FLUJO:
        1. Configurar cluster(s) de Kubernetes
        2. Crear templates de manifiestos YAML
        3. Crear planes con recursos y templates
        4. Crear instancias seleccionando cluster y plan
    """,
    'author': 'AutomateAI',
    'website': 'https://automateai.com.mx',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'sale_management',
        'sale_subscription',
        'saas_services',
    ],
    'data': [
        # Security
        'security/k8s_saas_security.xml',
        'security/ir.model.access.csv',
        # Views
        'views/k8s_cluster_views.xml',
        'views/k8s_manifest_template_views.xml',
        'views/k8s_instance_plan_views.xml',
        'views/k8s_instance_views.xml',
        'views/k8s_instance_manifest_views.xml',
        'views/k8s_menus.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        # Data
        'data/k8s_config_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['kubernetes', 'pyyaml', 'psycopg2-binary'],
    },
}
