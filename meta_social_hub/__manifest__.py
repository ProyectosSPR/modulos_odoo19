# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Meta Social Hub',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Social Marketing',
    'summary': 'Unified inbox for Facebook, Instagram, WhatsApp and Messenger',
    'description': """
Meta Social Hub - Unified Communication Platform
=================================================

This module provides a unified inbox to manage all Meta platform communications:

Features:
---------
* **Unified Inbox**: Single view to manage all conversations from Facebook, Instagram, WhatsApp and Messenger
* **WhatsApp Integration**: Full integration with WhatsApp Business API (extends existing module)
* **Facebook Messenger**: New integration for Facebook Page Messenger chats
* **Instagram DM**: Direct messages from Instagram accounts
* **CRM Integration**: Create leads directly from conversations
* **Sales Integration**: Send products and quotations via chat
* **Helpdesk Integration**: Create support tickets from conversations
* **Contact Management**: Link conversations to partners automatically

Requirements:
-------------
* Odoo Enterprise 19.0
* Meta Business Suite account
* Facebook App with Messenger Platform enabled
* WhatsApp Business API access

Phase 2 (Future):
-----------------
* AI-powered automatic responses (meta_social_ai module)
* Message classification and routing
* Sentiment analysis
    """,
    'author': 'IT Admin',
    'website': 'https://www.itadmin.mx',
    'license': 'LGPL-3',
    'depends': [
        # Odoo Enterprise Social modules
        'social',
        'social_facebook',
        'social_instagram',
        'whatsapp',
        # CRM & Sales
        'crm',
        'sale_management',
        # Helpdesk & Projects
        'helpdesk',
        'project',
        # Products
        'product',
        # Base
        'mail',
        'contacts',
    ],
    'data': [
        # Security
        'security/meta_social_hub_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/ir_cron_data.xml',
        'data/meta_channel_data.xml',
        # Views
        'views/meta_channel_views.xml',
        'views/meta_conversation_views.xml',
        'views/meta_message_views.xml',
        'views/inbox_views.xml',
        'views/res_partner_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
        # Wizards
        'wizards/send_product_wizard_views.xml',
        'wizards/create_lead_wizard_views.xml',
        'wizards/create_ticket_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'meta_social_hub/static/src/scss/inbox_style.scss',
            'meta_social_hub/static/src/js/inbox_kanban.js',
            'meta_social_hub/static/src/js/conversation_view.js',
            'meta_social_hub/static/src/xml/inbox_templates.xml',
            'meta_social_hub/static/src/xml/conversation_templates.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
