# -*- coding: utf-8 -*-
{
    'name': 'InEstetica - Sitio Web Medicina Estetica',
    'summary': 'Sitio web publico para centro de medicina estetica con agendamiento de citas',
    'description': """
        Sitio web profesional para centro de medicina estetica:
        - Pagina principal con hero, tratamientos faciales y corporales, proceso, bio del especialista
        - Wizard de reserva de cita en 4 pasos conectado a la agenda
        - Diseno responsive, claro y vibrante (paleta rosa-magenta + coral)
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Healthcare',
    'version': '18.0.1.0.0',
    'depends': [
        'website',
        'in_estetica_agenda',
    ],
    'data': [
        'views/homepage_templates.xml',
        'views/frontend_apps_dropdown.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_frontend': [
            'in_estetica_web/static/src/scss/homepage.scss',
            'in_estetica_web/static/src/js/scroll_animations.js',
            'in_estetica_web/static/src/js/wizard.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}