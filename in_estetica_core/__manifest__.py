# -*- coding: utf-8 -*-
{
    'name': 'Innatum Estética - Core',
    'summary': 'Base del proyecto Estética: roles, colaboradores, menús '
               'administrativos',
    'description': """
        Innatum Estética Core — Módulo base del producto.

        Define los 3 roles de seguridad del centro de medicina estética como
        permisos tipo check independientes:
        Médico estético, Secretaria/Recepción, Administrador.

        Expone el menú "Administración > Colaboradores" dentro del grupo
        MUK "Administración Estética" con vistas propias (tree + form)
        sobre hr.employee. La alta se hace por un wizard único que crea
        empleado + usuario + asignación de grupo.

        El menú nativo de HR queda restringido a base.group_system para
        evitar duplicidad de interfaz.
    """,
    'author': 'Innatum',
    'website': 'https://www.innatum.com',
    'category': 'Services',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'mail',
        'hr',
        'muk_web_appsbar',
        'in_estetica_control',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'wizard/wizard_nuevo_colaborador_views.xml',
        'views/hr_employee_colaborador_views.xml',
        'views/menus.xml',
        'views/menu_groups_muk.xml',
        'views/hr_menu_hide.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
}
