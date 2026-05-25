# -*- coding: utf-8 -*-
{
    'name': 'RENOVA Backend Theme',
    'summary': 'Tematica carbon/rose-gold RENOVA para el backend de Odoo',
    'description': """
        Aplica la paleta del sitio web (carbon, rose-gold, blanco) al backend
        de Odoo: navbar, appsbar, formularios, listas, botones y tipografia
        Playfair Display + Inter.

        No depende de muk_web_theme; sobrescribe variables nativas de Odoo
        en el bundle _assets_primary_variables.
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Themes/Backend',
    'version': '18.0.1.0.0',
    'depends': [
        'web',
        'muk_web_appsbar',
    ],
    'data': [
        'views/web_layout.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('after',
             'web/static/src/scss/primary_variables.scss',
             'in_estetica_backend_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'in_estetica_backend_theme/static/src/scss/backend.scss',
            'in_estetica_backend_theme/static/src/js/cursor.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
