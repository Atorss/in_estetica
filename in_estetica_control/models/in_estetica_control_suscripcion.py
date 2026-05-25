# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class InControlSuscripcion(models.Model):
    """Suscripción de cliente operada por Innatum.

    Vincula una company con una vigencia (fecha_inicio / fecha_fin) y un
    margen IA aplicable a las recargas. Permite histórico: pueden coexistir
    varias suscripciones para la misma company a lo largo del tiempo, pero
    solo una activa simultáneamente.

    Al vencer la fecha_fin el cron marca la suscripción como 'expired' y
    desactiva los usuarios de la company del cliente (hard expire),
    preservando al admin Innatum y al superuser.
    """
    _name = 'in_estetica_control.suscripcion'
    _description = 'Suscripción Innatum'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Referencia', required=True, copy=False,
        readonly=True, default='Nueva',
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        ondelete='restrict', index=True, tracking=True,
        default=lambda self: self.env.company,
    )
    fecha_inicio = fields.Date(
        string='Inicio', required=True, tracking=True,
        default=fields.Date.today,
    )
    fecha_fin = fields.Date(
        string='Fin', required=True, tracking=True,
        help='Al vencer, el cron diario marca la suscripción como '
             '"Vencida" y desactiva los usuarios de la empresa.',
    )
    ai_margin_pct = fields.Float(
        string='Margen IA (%)', digits=(5, 2), default=50.0, tracking=True,
        help='Margen de Innatum sobre el monto cobrado en cada recarga. '
             'Snapshot del valor vigente al crear la recarga.',
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activa'),
        ('suspended', 'Suspendida'),
        ('expired', 'Vencida'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='active', required=True, tracking=True)

    recarga_ids = fields.One2many(
        'in_estetica_control.recarga_ia', 'suscripcion_id',
        string='Recargas IA',
    )
    recarga_count = fields.Integer(compute='_compute_recarga_aggregates')
    tokens_disponibles_total_usd = fields.Float(
        string='Disponible total (USD)',
        compute='_compute_recarga_aggregates', digits=(12, 4),
    )
    tokens_consumidos_total_usd = fields.Float(
        string='Consumido total (USD)',
        compute='_compute_recarga_aggregates', digits=(12, 4),
    )
    tokens_restantes_total_usd = fields.Float(
        string='Restante total (USD)',
        compute='_compute_recarga_aggregates', digits=(12, 4),
    )

    notes = fields.Text(string='Notas internas')
    active = fields.Boolean(default=True)

    tiene_admin_consultorio = fields.Boolean(
        string='Tiene admin del consultorio',
        compute='_compute_tiene_admin_consultorio',
        help='True si la empresa ya tiene al menos un usuario activo con '
             'el grupo "Administrador" del clínica estética.',
    )

    # ------------------------------------------------------------------
    # Computados
    # ------------------------------------------------------------------

    @api.depends('recarga_ids',
                 'recarga_ids.tokens_disponibles_usd',
                 'recarga_ids.tokens_consumidos_usd',
                 'recarga_ids.tokens_restantes_usd')
    def _compute_recarga_aggregates(self):
        for rec in self:
            recs = rec.recarga_ids
            rec.recarga_count = len(recs)
            rec.tokens_disponibles_total_usd = sum(recs.mapped('tokens_disponibles_usd'))
            rec.tokens_consumidos_total_usd = sum(recs.mapped('tokens_consumidos_usd'))
            rec.tokens_restantes_total_usd = sum(recs.mapped('tokens_restantes_usd'))

    @api.depends('company_id')
    def _compute_tiene_admin_consultorio(self):
        """True si existe un hr.employee con rol='administrador' vinculado
        a un usuario activo en la company de la suscripción.

        Usamos hr.employee + rol (en vez de contar usuarios con el grupo
        de seguridad) porque el superuser de Odoo y los admin Innatum
        técnicamente "tienen" el grupo administrador pero no son
        administradores reales del consultorio. Solo cuentan los que se
        crearon a través del wizard de alta de colaboradores.

        El campo `rol` lo aporta in_estetica_core. Detectamos la
        presencia dinámicamente para no romper si core no está instalado
        (en cuyo caso el botón queda permanentemente oculto, que es lo
        deseado: no se puede crear el admin sin el módulo que define el
        wizard).
        """
        # OJO: NO usar bool(Employee) para el check de existencia — la
        # truthiness de un recordset evalúa "tiene registros", no "el
        # modelo existe". Verificamos por membresía en self.env.
        has_employee = 'hr.employee' in self.env
        Employee = self.env['hr.employee'] if has_employee else None
        has_rol_field = has_employee and 'rol' in Employee._fields
        for rec in self:
            if not has_rol_field or not rec.company_id:
                rec.tiene_admin_consultorio = False
                continue
            rec.tiene_admin_consultorio = bool(
                Employee.sudo().search_count([
                    ('rol', '=', 'administrador'),
                    ('company_id', '=', rec.company_id.id),
                    ('active', '=', True),
                    ('user_id', '!=', False),
                    ('user_id.active', '=', True),
                ])
            )

    # ------------------------------------------------------------------
    # Constrains
    # ------------------------------------------------------------------

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_fin < rec.fecha_inicio:
                raise ValidationError(_(
                    'La fecha "Fin" debe ser mayor o igual a "Inicio".'
                ))

    @api.constrains('ai_margin_pct')
    def _check_margin(self):
        for rec in self:
            if not (0 <= rec.ai_margin_pct <= 100):
                raise ValidationError(_(
                    'El margen IA debe estar entre 0 y 100%.'
                ))

    @api.constrains('company_id', 'state')
    def _check_unica_activa_por_company(self):
        for rec in self:
            if rec.state not in ('draft', 'active'):
                continue
            otras = self.search([
                ('company_id', '=', rec.company_id.id),
                ('state', 'in', ('draft', 'active')),
                ('id', '!=', rec.id),
            ])
            if otras:
                raise ValidationError(_(
                    'La empresa "%(name)s" ya tiene una suscripción activa: '
                    '%(ref)s. Solo puede haber una activa a la vez — vence '
                    'o cancela la anterior antes de crear otra.',
                    name=rec.company_id.name, ref=otras[0].name,
                ))

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                seq = self.env['ir.sequence'].next_by_code('in_estetica_control.suscripcion')
                vals['name'] = seq or 'SUSC/0001'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # API pública usada por el gate IA
    # ------------------------------------------------------------------

    @api.model
    def _get_active_for_company(self, company):
        """Devuelve la suscripción activa de una company o recordset vacío.

        Usado por el gate del motor IA antes de cada llamada.
        Corre con sudo: el motor IA puede invocarse desde contextos donde
        el usuario actual no tiene acceso directo al modelo de suscripción.
        """
        if not company:
            return self.browse()
        return self.sudo().search([
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
            ('active', '=', True),
        ], limit=1)

    @api.model
    def _has_ai_credit_for_company(self, company):
        """True si la company tiene saldo IA disponible.

        Usado para decidir si renderizar widgets/funcionalidades IA en el
        front. Evita mostrar UI que va a fallar al primer click.
        """
        if not company:
            return False
        susc = self._get_active_for_company(company)
        if not susc:
            return False
        return susc.tokens_restantes_total_usd > 0

    # ------------------------------------------------------------------
    # Acciones de UI
    # ------------------------------------------------------------------

    def action_view_recargas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recargas IA — %s') % self.name,
            'res_model': 'in_estetica_control.recarga_ia',
            'view_mode': 'list,form',
            'domain': [('suscripcion_id', '=', self.id)],
            'context': {'default_suscripcion_id': self.id},
        }

    def action_crear_primer_admin(self):
        """Abre el wizard de alta de colaborador con rol pre-seleccionado
        a 'administrador'.

        El wizard vive en in_estetica_core. Para no agregar dependencia
        inversa (que sería ciclo, ya que core depende de control), lo
        invocamos por referencia dinámica:
          - chequeo de existencia del modelo en self.env
          - apertura por act_window con view_id resuelto por env.ref
        Si in_estetica_core no está instalado, el botón en la vista
        queda oculto (tiene_admin_consultorio requiere el grupo del rol
        administrador, que solo existe con core instalado).
        """
        self.ensure_one()
        wizard_model = 'in_estetica_core.wizard_nuevo_colaborador'
        if wizard_model not in self.env:
            raise UserError(_(
                'El módulo "Innatum Estética - Core" no está instalado. '
                'Instalalo antes de dar de alta colaboradores.'
            ))
        if self.tiene_admin_consultorio:
            raise UserError(_(
                'La empresa "%s" ya tiene un administrador del consultorio. '
                'Da de alta colaboradores adicionales desde el menú '
                '"Colaboradores > Nuevo Colaborador".'
            ) % self.company_id.name)
        view = self.env.ref(
            'in_estetica_core.view_wizard_nuevo_colaborador_form',
            raise_if_not_found=False,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear primer administrador'),
            'res_model': wizard_model,
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'target': 'new',
            'context': {
                'default_rol': 'administrador',
            },
        }

    def action_activar(self):
        for rec in self:
            if rec.state in ('active',):
                continue
            rec.state = 'active'
            rec._reactivar_usuarios_company()

    def action_suspender(self):
        for rec in self:
            rec.state = 'suspended'

    def action_cancelar(self):
        for rec in self:
            rec.state = 'cancelled'

    # ------------------------------------------------------------------
    # Hard expire: desactivación / reactivación de usuarios
    # ------------------------------------------------------------------

    def _users_protegidos_ids(self):
        """IDs de usuarios que NUNCA deben ser desactivados por el cron.

        Protege:
        - Superuser (id=1)
        - Cualquier usuario con grupo 'in_estetica_control.group_innatum_admin' (admin Innatum)
        - El propio usuario que ejecuta la acción
        """
        protegidos = {1, self.env.uid}
        admin_group = self.env.ref(
            'in_estetica_control.group_innatum_admin', raise_if_not_found=False,
        )
        if admin_group:
            protegidos.update(admin_group.users.ids)
        return list(protegidos)

    def _desactivar_usuarios_company(self):
        """Desactiva users internos de la company, excluyendo protegidos."""
        self.ensure_one()
        protegidos = self._users_protegidos_ids()
        users = self.env['res.users'].sudo().search([
            ('share', '=', False),
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
            ('id', 'not in', protegidos),
        ])
        if users:
            users.write({'active': False})
            _logger.info(
                'in_estetica_control.suscripcion %s: %d usuarios desactivados '
                '(company %s).', self.name, len(users), self.company_id.name,
            )

    def _reactivar_usuarios_company(self):
        """Reactiva users de la company que fueron desactivados.

        No reactiva indiscriminadamente: solo users desactivados que NO
        están en la lista de protegidos. Si un admin desactivó alguno
        manualmente por otro motivo, se va a reactivar también — limitación
        consciente (no llevamos registro del motivo de desactivación).
        """
        self.ensure_one()
        users = self.env['res.users'].sudo().search([
            ('share', '=', False),
            ('active', '=', False),
            ('company_id', '=', self.company_id.id),
            ('id', '!=', 1),
        ])
        if users:
            users.write({'active': True})
            _logger.info(
                'in_estetica_control.suscripcion %s: %d usuarios reactivados '
                '(company %s).', self.name, len(users), self.company_id.name,
            )

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    @api.model
    def _cron_verificar_vencimiento(self):
        """Marca como expired y bloquea login (hard expire) al vencer."""
        hoy = fields.Date.today()
        vencidas = self.search([
            ('state', '=', 'active'),
            ('fecha_fin', '<', hoy),
        ])
        for susc in vencidas:
            susc.state = 'expired'
            susc._desactivar_usuarios_company()
            susc.message_post(body=_(
                'Suscripción vencida automáticamente. Usuarios de la '
                'empresa desactivados (admin Innatum preservado).'
            ))
        if vencidas:
            _logger.info(
                'Cron in_estetica_control: %d suscripciones vencidas procesadas.',
                len(vencidas),
            )
        return True
