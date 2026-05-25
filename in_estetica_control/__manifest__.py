# -*- coding: utf-8 -*-
{
    'name': 'Innatum Estética - Control',
    'summary': 'Suscripciones y recargas IA para el proyecto Estética',
    'description': """
        Innatum Estética Control — Capa interna de Innatum para el
        proyecto Estética.

        Permite registrar suscripciones por empresa (con fecha inicio/fin
        y margen IA) y recargas de saldo IA. El consumo de IA se imputa
        FIFO contra las recargas usando innatum.ai.usage.log como fuente
        de verdad.

        Al vencer la fecha_fin (hard expire) el cron desactiva los usuarios
        de la empresa preservando al admin Innatum y al superuser.
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Services',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'mail',
        'innatum_ai',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/cron.xml',
        'views/in_estetica_control_suscripcion_views.xml',
        'views/in_estetica_control_recarga_ia_views.xml',
        'views/menus.xml',
        'data/menu_groups_innatum.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
