# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

# Menus que debe tener el sitio web de RENOVA. (name, url, sequence)
# El name esta en es_EC; al crearlo Odoo lo guarda como translatable.
MENUS = [
    ('Inicio',          '/',              10),
    ('Especialista',    '/#equipo',       20),
    ('Proceso',         '/#metodologia',  25),
    ('Tratamientos',    '/#servicios',    30),
    ('Contacto',        '/#contacto',     60),
]


def _ensure_menus(env):
    """Asegura que el menu del sitio web contenga exactamente los items
    de RENOVA, colgados del menu raiz de CADA website existente.

    - Funciona en BD limpia (post_init) y en BD con datos (manual).
    - Borra los menus default 'Inicio' y 'Contact us' que crea el core.
    - Idempotente: si ya existen, los actualiza.
    """
    Menu = env['website.menu'].sudo()
    Website = env['website'].sudo()

    websites = Website.search([])
    if not websites:
        _logger.warning('RENOVA: no hay websites configurados, salto menus.')
        return

    for website in websites:
        root = website.menu_id
        if not root:
            _logger.warning(
                'RENOVA: website %s sin menu raiz, lo salto.', website.id
            )
            continue

        # 1. Borrar los menus default que crea el core (Inicio, Contact us)
        #    SOLO los que tienen url '/' o '/contactus' y NO coinciden con
        #    los nuestros (los reemplazaremos).
        defaults = Menu.search([
            ('parent_id', '=', root.id),
            ('url', 'in', ['/', '/contactus']),
        ])
        # No borramos los que ya creamos nosotros (mismos urls al sequence
        # custom 10 y 60). Comparamos por sequence + url:
        for d in defaults:
            keep = any(
                d.url == url and d.sequence == seq
                for (_n, url, seq) in MENUS
            )
            if not keep:
                d.unlink()

        # 2. Crear/actualizar los 5 menus de RENOVA
        for name, url, sequence in MENUS:
            existing = Menu.search([
                ('parent_id', '=', root.id),
                ('url', '=', url),
            ], limit=1)
            vals = {
                'name': name,
                'url': url,
                'sequence': sequence,
                'parent_id': root.id,
                'website_id': website.id,
            }
            if existing:
                existing.write(vals)
            else:
                Menu.create(vals)

    _logger.info(
        'RENOVA: menus del website provisionados en %d sites.',
        len(websites),
    )


def post_init_hook(env):
    """Crea/actualiza los menus al instalar el modulo."""
    _ensure_menus(env)


def uninstall_hook(env):
    """Limpia los menus de RENOVA al desinstalar para no dejar basura."""
    Menu = env['website.menu'].sudo()
    urls = [url for (_n, url, _s) in MENUS if url != '/']  # no borrar /
    Menu.search([('url', 'in', urls)]).unlink()