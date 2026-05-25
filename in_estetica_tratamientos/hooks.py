# -*- coding: utf-8 -*-
"""Hooks de instalación.

- Asocia el menú raíz "Tratamientos" al grupo MUK (reutiliza el grupo de
  "Atención" del agenda, renombrándolo a "Tratamientos").
- Desactiva el menú clínico heredado de nutrición ("Atención Clínica":
  consultas, planes, catálogos clínicos, etc.) que no aplica a medicina
  estética, para no dejar opciones que confundan al usuario.
"""

import base64
import logging

from odoo.tools import file_open

_logger = logging.getLogger(__name__)


def _set_group_icon(grupo, module_path):
    """Asigna el icono (Binary) de un ir.ui.menu.group desde un PNG del módulo."""
    if not grupo:
        return
    try:
        with file_open(module_path, 'rb') as f:
            grupo.icon = base64.b64encode(f.read())
    except Exception:
        _logger.warning('No se pudo cargar el icono de grupo %s', module_path)


def post_init_hook(env):
    # 1. Reutilizar y renombrar el grupo MUK a "Tratamientos"
    #    (el grupo lo define in_estetica_agenda en menu_groups_atencion.xml)
    grupo = env.ref('in_estetica_agenda.menu_group_atencion_nutricional',
                    raise_if_not_found=False)
    menu = env.ref('in_estetica_tratamientos.menu_tratamientos_root',
                   raise_if_not_found=False)
    if grupo:
        grupo.name = 'Tratamientos'
        _set_group_icon(grupo, 'in_estetica_tratamientos/static/description/icon.png')
        if menu and menu not in grupo.menu_ids:
            grupo.write({'menu_ids': [(4, menu.id)]})

    # Icono del grupo "Administración Estética"
    _set_group_icon(
        env.ref('muk_web_appsbar.menu_group_medic_administracion',
                raise_if_not_found=False),
        'in_estetica_core/static/img/administracion_estetica.png',
    )

    # 2. Desactivar el menú clínico de nutrición (consultas/planes/catálogos)
    menu_nutri = env.ref('in_estetica_agenda.menu_atencion_root',
                         raise_if_not_found=False)
    if menu_nutri and menu_nutri.active:
        menu_nutri.active = False
        _logger.info('in_estetica_tratamientos: menú "Atención Clínica" '
                     '(nutrición) desactivado.')
