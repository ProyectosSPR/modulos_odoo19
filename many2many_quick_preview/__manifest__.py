{
    'name': 'Many2Many Quick Preview',
    'author': 'Odoo Hub',
    'category': 'Tools',
    'summary': 'Provides quick preview of records in many2many_tags, many2many preview many2many clickable odoo record preview many2many field preview many2many field clickable many2many tags clickable many2many_tags clickable many2many_tags preview tags preview tags clickable clickable tag quick preview odoo many2many quick view instant record preview odoo related records preview many2many smart preview preview related records odoo many2many instant access many2many detail preview many2many inline preview quick access to records odoo productivity enhancement odoo preview without opening record preview on hover odoo ui enhancement many2many relation preview clickable many2many tags many2many record access preview in tags odoo improve navigation many2many quick detail view',
    'description': """
        Many2Many Quick Preview is an Odoo app that allows users to instantly preview related records in many2many fields directly from the many2many_tags. 
        This app improves navigation and productivity by providing quick access to record details without having to open them individually.
    """,
    'maintainer': 'Odoo Hub',
    'website': 'https://apps.odoo.com/apps/modules/browse?author=Odoo%20Hub',
    'version': '1.0',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'many2many_quick_preview/static/src/js/many2many_tags_field.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'live_test_url': 'https://youtu.be/dNF106wVNX0',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
