{
    'name': 'SaaS Team Management',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Freelancers',
    'summary': 'Gestión de colaboradores y freelancers como usuarios de portal',
    'description': """
        Módulo para gestionar colaboradores/freelancers:
        - Colaboradores como usuarios de portal (sin licencia)
        - Asignación de proyectos usando Project Sharing nativo
        - Gestión de pagos y balance
        - Skills y especialidades
        - Formulario de aplicación web
    """,
    'author': 'AutomateAI',
    'website': 'https://automateai.com.mx',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'portal',
        'website',
        'project',
        'hr_timesheet',
        'appointment',
        'saas_services',
    ],
    'data': [
        'security/saas_team_security.xml',
        'security/ir.model.access.csv',
        'data/saas_skill_data.xml',
        'data/mail_templates.xml',
        'wizard/add_collaborator_wizard_views.xml',
        'views/saas_collaborator_views.xml',
        'views/saas_skill_views.xml',
        'views/saas_payment_views.xml',
        'views/saas_team_menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
