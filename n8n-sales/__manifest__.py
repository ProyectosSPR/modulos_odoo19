# -*- coding: utf-8 -*-
{
    'name': "N8N Sales",
    'summary': "Vende y gestiona automatizaciones de n8n como productos.",
    'description': """
        Este módulo integra Odoo con n8n para permitir la venta de workflows de automatización.
        - Crea usuarios en n8n al confirmar una venta.
        - Permite a los clientes sincronizar workflows desde el portal.
        - Configuración dinámica de nodos del workflow.
        - Portal completo para gestión de automatizaciones.
    """,
    'author': "Automateai",
    'website': "https://automateai.com.mx",
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
        'website',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/n8n_workflow_instance_security.xml',
        'wizards/n8n_sync_wizard_views.xml',
        'views/n8n_workflow_instance_views.xml',
        'views/product_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/n8n_menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
}

