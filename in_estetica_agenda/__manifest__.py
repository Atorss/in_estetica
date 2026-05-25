# -*- coding: utf-8 -*-
{
    'name': 'Innatum Estética - Agenda',
    'summary': 'Agenda, turnos, pacientes y atención de medicina estética',
    'description': """
        Módulo de agenda y atención para el centro de medicina estética.

        MOTOR DE AGENDAMIENTO (reutilizado de Nutrición, genérico):
        - Tipos de cita (catálogo configurable).
        - Planificaciones (rango de fechas + tramos por día → genera turnos).
        - Turnos con estados available → reserved → confirmed → in_progress
          → done / cancelled. Anti doble-booking y vista calendario.
        - Pacientes (in_estetica.paciente con _inherits res.partner).

        CAPA CLÍNICA (clonada como plantilla — pendiente de re-modelar al
        dominio de medicina estética en la Fase 5: consultas, anamnesis,
        catálogos clínicos y planes aún reflejan el dominio nutricional original).

        Dos menús raíz:
          · Agenda (compartido: médico estético, secretaria, admin)
          · Atención Clínica (clínico: médico estético + admin)
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Services',
    'version': '18.0.2.0.0',
    'depends': [
        'base',
        'mail',
        'in_estetica_core',
        'in_estetica_control',
        'muk_web_appsbar',
    ],
    'external_dependencies': {
        'python': ['pytz'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'data/sequences.xml',
        'data/tipo_cita_data.xml',
        'data/menu_groups_atencion.xml',
        'views/in_estetica_tipo_cita_views.xml',
        'views/in_estetica_planificacion_views.xml',
        'views/in_estetica_paciente_views.xml',
        'views/in_estetica_turno_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
