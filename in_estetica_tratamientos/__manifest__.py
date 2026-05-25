# -*- coding: utf-8 -*-
{
    'name': 'Innatum Estética - Tratamientos',
    'summary': 'Control de tratamientos por sesiones y recordatorios de retoque',
    'description': """
        El corazón del centro de medicina estética: llevar el control de los
        tratamientos que se hace cada paciente, por TIPO de tratamiento, y
        saber cuántas sesiones necesita y cuántas lleva ("3 de 6").

        - Catálogo de tipos de tratamiento (Botox, Ácido hialurónico, Exosomas,
          Células madre, PDRN, Exilis, Láser, Limpiezas faciales, Fototerapia…)
          con sesiones recomendadas e intervalos entre sesiones y de retoque.
        - Tratamiento del paciente (curso): progreso de sesiones, próxima
          sesión calculada y estado (en curso / mantenimiento / completado).
        - Sesión: cada aplicación, registrada desde el turno atendido.
        - Recordatorios automáticos (cron): cuando toca la siguiente sesión o
          el retoque, crea una actividad interna para recepción y envía un
          email al paciente.
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Services',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'mail',
        'in_estetica_core',
        'in_estetica_agenda',
        'muk_web_appsbar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/tipos_tratamiento_data.xml',
        'data/mail_template.xml',
        'data/cron.xml',
        'views/in_estetica_tipo_tratamiento_views.xml',
        'views/in_estetica_tratamiento_views.xml',
        'views/in_estetica_sesion_views.xml',
        'views/in_estetica_turno_inherit_views.xml',
        'views/in_estetica_wizard_agendar_sesion_views.xml',
        'views/in_estetica_wizard_agregar_sesiones_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
