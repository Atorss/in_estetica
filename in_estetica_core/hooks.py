# -*- coding: utf-8 -*-
"""Hooks de instalación/upgrade.

post_init_hook: asocia el menú raíz 'Administración' al grupo MUK
'Administración Estética'. Defensivo porque el comando (4, ref(...))
sobre records de otros módulos no persiste de forma confiable en data
XML al hacer upgrade en Odoo 18.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    grupo = env.ref(
        'muk_web_appsbar.menu_group_medic_administracion',
        raise_if_not_found=False,
    )
    menu = env.ref(
        'in_estetica_core.menu_in_estetica_core_root',
        raise_if_not_found=False,
    )
    if not grupo or not menu:
        _logger.warning(
            'post_init_hook: referencias faltantes (grupo=%s, menu=%s).',
            grupo, menu,
        )
        return
    if menu in grupo.menu_ids:
        return
    grupo.write({'menu_ids': [(4, menu.id)]})
    _logger.info(
        'post_init_hook: menú "%s" asociado al grupo MUK "%s".',
        menu.complete_name, grupo.name,
    )
