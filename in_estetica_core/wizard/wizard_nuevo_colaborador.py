# -*- coding: utf-8 -*-
"""Wizard único para dar de alta un colaborador.

Crea de manera atómica: hr.employee + res.users + asignación del grupo
de seguridad según el rol elegido. Patrón inspirado en
innatum_agenda_planes.wizard_tenant_provisioning.
"""

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from ..models.hr_employee import ROL_GROUP_XMLID, ROL_SELECTION

_logger = logging.getLogger(__name__)


class WizardNuevoColaborador(models.TransientModel):
    _name = 'in_estetica_core.wizard_nuevo_colaborador'
    _description = 'Wizard: Nuevo Colaborador'

    name = fields.Char(string='Nombre completo', required=True)
    work_email = fields.Char(
        string='Correo de trabajo', required=True,
        help='Se usará como login del usuario.',
    )
    work_phone = fields.Char(string='Teléfono')
    rol = fields.Selection(
        ROL_SELECTION, string='Rol', required=True,
    )
    password = fields.Char(
        string='Contraseña inicial', required=True,
        help='Mínimo 8 caracteres. El colaborador debería cambiarla al '
             'primer login.',
    )

    @api.constrains('password')
    def _check_password(self):
        for rec in self:
            if rec.password and len(rec.password) < 8:
                raise ValidationError(_(
                    'La contraseña debe tener al menos 8 caracteres.'
                ))

    @api.constrains('work_email')
    def _check_email_format(self):
        for rec in self:
            if rec.work_email and '@' not in rec.work_email:
                raise ValidationError(_(
                    'Ingresa un email válido.'
                ))

    def action_crear(self):
        self.ensure_one()
        company = self.env.company

        if self.env['res.users'].sudo().search_count([
            ('login', '=', self.work_email),
        ]):
            raise ValidationError(_(
                'Ya existe un usuario con el correo "%s".'
            ) % self.work_email)

        rol_group = self.env.ref(
            ROL_GROUP_XMLID[self.rol], raise_if_not_found=True,
        )
        groups = [
            self.env.ref('base.group_user').id,
            rol_group.id,
        ]

        # 1. Crear usuario
        user = self.env['res.users'].sudo().with_context(
            no_reset_password=True,
        ).create({
            'name': self.name,
            'login': self.work_email,
            'email': self.work_email,
            'password': self.password,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'groups_id': [(6, 0, groups)],
        })
        user.partner_id.sudo().write({'company_id': company.id})

        # 2. Crear empleado vinculado
        employee = self.env['hr.employee'].sudo().create({
            'name': self.name,
            'work_email': self.work_email,
            'work_phone': self.work_phone or False,
            'rol': self.rol,
            'user_id': user.id,
            'company_id': company.id,
        })
        employee.message_post(body=_(
            'Colaborador creado con rol <b>%(rol)s</b> y acceso al sistema '
            '(login: <b>%(login)s</b>).'
        ) % {'rol': dict(ROL_SELECTION).get(self.rol), 'login': user.login})

        _logger.info(
            'in_estetica_core: colaborador creado emp=%s user=%s rol=%s',
            employee.id, user.id, self.rol,
        )

        # Redirigir al listado de colaboradores (no al form del recién
        # creado — desde el form aparecía el botón "Nuevo" del breadcrumb
        # que rompía la regla de "alta solo por wizard").
        action = self.env.ref(
            'in_estetica_core.action_hr_employee_colaborador'
        ).sudo().read()[0]
        return action
