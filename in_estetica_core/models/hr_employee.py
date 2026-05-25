# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


ROL_SELECTION = [
    ('secretaria', 'Secretaria / Recepción'),
    ('doctor', 'Médico estético'),
    ('administrador', 'Administrador'),
]

# Mapping rol → xmlid del grupo de seguridad. Centralizado acá para que el
# wizard de creación y el sync write usen la misma fuente.
ROL_GROUP_XMLID = {
    'doctor': 'in_estetica_core.group_doctor',
    'secretaria': 'in_estetica_core.group_secretaria',
    'administrador': 'in_estetica_core.group_administrador',
}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    rol = fields.Selection(
        ROL_SELECTION,
        string='Rol del colaborador',
        tracking=True,
        help='Rol funcional dentro del consultorio. Determina qué grupo de '
             'seguridad recibe el usuario asociado.',
    )

    def write(self, vals):
        """Sync con res.users del colaborador.

        - work_email → user.login + user.email (válida unicidad de login).
        - rol → user.groups_id (quita el grupo del rol anterior y agrega
          el del nuevo). Si el rol pasa a vacío solo quita el grupo viejo.
        """
        # Snapshot del rol previo para el diff post-write
        old_rol_by_id = {}
        if 'rol' in vals:
            for emp in self:
                old_rol_by_id[emp.id] = emp.rol

        result = super().write(vals)

        if 'work_email' not in vals and 'rol' not in vals:
            return result

        for emp in self:
            if not emp.user_id:
                continue

            # --- 1. Sync de email/login ---
            if 'work_email' in vals and emp.work_email:
                if emp.user_id.login != emp.work_email:
                    duplicado = self.env['res.users'].sudo().search_count([
                        ('login', '=', emp.work_email),
                        ('id', '!=', emp.user_id.id),
                    ])
                    if duplicado:
                        raise ValidationError(_(
                            'Ya existe otro usuario con el login "%s". '
                            'Elige un correo distinto.'
                        ) % emp.work_email)
                    emp.user_id.sudo().write({
                        'login': emp.work_email,
                        'email': emp.work_email,
                    })
                    _logger.info(
                        'in_estetica_core: login sincronizado emp=%s '
                        'user=%s nuevo_login=%s',
                        emp.id, emp.user_id.id, emp.work_email,
                    )

            # --- 2. Sync de rol/grupos ---
            if 'rol' in vals:
                old_rol = old_rol_by_id.get(emp.id)
                new_rol = emp.rol
                if old_rol == new_rol:
                    continue
                ops = []
                if old_rol and old_rol in ROL_GROUP_XMLID:
                    old_g = self.env.ref(
                        ROL_GROUP_XMLID[old_rol], raise_if_not_found=False,
                    )
                    if old_g:
                        ops.append((3, old_g.id))
                if new_rol and new_rol in ROL_GROUP_XMLID:
                    new_g = self.env.ref(
                        ROL_GROUP_XMLID[new_rol], raise_if_not_found=False,
                    )
                    if new_g:
                        ops.append((4, new_g.id))
                if ops:
                    emp.user_id.sudo().write({'groups_id': ops})
                    _logger.info(
                        'in_estetica_core: rol sincronizado emp=%s '
                        'user=%s %s → %s',
                        emp.id, emp.user_id.id, old_rol, new_rol,
                    )

        return result
