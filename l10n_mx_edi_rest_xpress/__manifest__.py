# -*- coding: utf-8 -*-
{
    'name': 'Mexico - REST XPRESS PAC',
    'version': '19.0.1.1.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'PAC REST XPRESS (Timbrador Xpress) connector for Mexican electronic invoicing',
    'description': """
REST XPRESS PAC Integration
============================

This module adds REST XPRESS (Timbrador Xpress) as a PAC (Proveedor Autorizado de Certificación)
option for Mexican electronic invoicing (CFDI 4.0).

Features:
---------
* JSON-based stamping (timbrado) via REST API
* Support for all CFDI types (Ingreso, Egreso, Traslado, Pago, Nómina)
* Support for CFDI complements (Carta Porte, Comercio Exterior, etc.)
* PDF generation with customizable fields
* Logo support
* Cancellation support with SAT cancellation reasons (cancelarPEM endpoint)
* Available credits (timbres) query from configuration
* SAT status query for CFDIs

Configuration:
-------------
1. Go to Accounting > Configuration > Settings
2. Under "Mexican Localization", select "REST XPRESS (Timbrador Xpress)" as PAC
3. Enter your REST XPRESS API Key in the Password field
4. Configure your CSD certificates as usual
5. Use "Consultar Créditos" button to check available stamps

Technical Details:
-----------------
* Converts Odoo's CFDI XML to REST XPRESS JSON format
* Uses Enterprise's certificate.certificate model
* Fully integrated with l10n_mx_edi EDI framework
* Compatible with all Enterprise PACs (Finkok, SW, Solfact, etc.)
* Uses cancelarPEM endpoint for cancellations (PEM format certificates)
* Uses consultarCreditosDisponibles endpoint to query credits
* Uses consultarEstadoSAT endpoint to query CFDI status
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'l10n_mx_edi',
        'account_edi',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
