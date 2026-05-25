# -*- coding: utf-8 -*-
"""Hooks de instalación/upgrade.

post_init_hook: garantiza que el menú raíz 'Administración' quede asociado
al grupo 'Innatum' de la sidebar MUK. Se hace acá porque el comando
(4, ref(...)) dentro de `eval` en data XML para records de otros módulos
no persiste de forma confiable en Odoo 18 al actualizar el módulo (sí
funciona desde Python). Reaplicarlo en cada install/upgrade es idempotente.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Asocia el menú raíz de in_estetica_control al grupo Innatum."""
    grupo = env.ref(
        'muk_web_appsbar.menu_group_innatum', raise_if_not_found=False,
    )
    menu = env.ref(
        'in_estetica_control.menu_in_estetica_control_root',
        raise_if_not_found=False,
    )
    if not grupo or not menu:
        _logger.warning(
            'post_init_hook: no se encontraron referencias '
            '(grupo=%s, menu=%s) — no se actualiza la asociación.',
            grupo, menu,
        )
        return
    if menu in grupo.menu_ids:
        return
    grupo.write({'menu_ids': [(4, menu.id)]})
    _logger.info(
        'post_init_hook: menú "%s" asociado al grupo "%s".',
        menu.complete_name, grupo.name,
    )
