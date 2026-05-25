# -*- coding: utf-8 -*-
"""post_init_hook:
- Asocia el menú "Agenda" al grupo MUK "Administración Estética".
- Asocia el menú "Atención Clínica" al grupo MUK del mismo nombre
  (definido en data/menu_groups_atencion.xml de este propio módulo).

Patrón defensivo: el eval declarativo `(4, ref(...))` no persiste de
forma confiable en Odoo 18 cuando el record M2M vive en otro módulo,
así que asociamos por hook explícito (idempotente).
"""

import logging

_logger = logging.getLogger(__name__)


def _asociar_menu_a_grupo(env, grupo_xmlid, menu_xmlid):
    grupo = env.ref(grupo_xmlid, raise_if_not_found=False)
    menu = env.ref(menu_xmlid, raise_if_not_found=False)
    if not grupo or not menu:
        _logger.warning(
            'post_init_hook agenda: referencias faltantes '
            '(grupo=%s [%s], menu=%s [%s]).',
            grupo_xmlid, grupo, menu_xmlid, menu,
        )
        return
    if menu in grupo.menu_ids:
        return
    grupo.write({'menu_ids': [(4, menu.id)]})
    _logger.info(
        'post_init_hook agenda: menú "%s" asociado al grupo MUK "%s".',
        menu.complete_name, grupo.name,
    )


def post_init_hook(env):
    # Agenda (compartida con Colaboradores en el grupo "Administración Estética")
    _asociar_menu_a_grupo(
        env,
        'muk_web_appsbar.menu_group_medic_administracion',
        'in_estetica_agenda.menu_agenda_root',
    )
