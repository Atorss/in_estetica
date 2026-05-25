# -*- coding: utf-8 -*-

import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class InEsteticaTratamiento(models.Model):
    """Tratamiento (curso) de un paciente: el control de sesiones.

    Es el modelo central del centro de medicina estética. Agrupa las
    sesiones de un mismo tipo de tratamiento para un paciente y permite
    ver el progreso ("3 de 6"), calcular la próxima sesión y disparar
    recordatorios cuando toca la siguiente sesión o el retoque.
    """
    _name = 'in_estetica.tratamiento'
    _description = 'Tratamiento del paciente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Referencia', readonly=True, copy=False, default='Nuevo',
    )
    paciente_id = fields.Many2one(
        'in_estetica.paciente', string='Paciente', required=True,
        ondelete='restrict', tracking=True, index=True,
    )
    tipo_tratamiento_id = fields.Many2one(
        'in_estetica.tipo_tratamiento', string='Tipo de tratamiento',
        required=True, tracking=True,
    )
    doctor_id = fields.Many2one(
        'hr.employee', string='Médico', tracking=True,
        domain="[('rol', '=', 'doctor')]",
        default=lambda self: self._default_doctor(),
    )
    fecha_inicio = fields.Date(
        string='Inicio', default=fields.Date.today, tracking=True,
    )
    sesiones_totales = fields.Integer(
        string='Sesiones planificadas', tracking=True,
        help='Total de sesiones para este tratamiento. Se propone desde el '
             'tipo, pero se puede ajustar.',
    )
    sesion_ids = fields.One2many(
        'in_estetica.tratamiento.sesion', 'tratamiento_id', string='Sesiones',
    )
    # Turnos pendientes (reservados/confirmados/en curso) del paciente —
    # espejo de los turnos agendados del paciente, solo lectura.
    turno_pendiente_ids = fields.One2many(
        related='paciente_id.turno_ids',
        string='Turnos pendientes del paciente', readonly=True,
    )

    sesiones_realizadas = fields.Integer(
        string='Sesiones realizadas', compute='_compute_progreso', store=True,
    )
    sesiones_restantes = fields.Integer(
        string='Sesiones restantes', compute='_compute_progreso', store=True,
    )
    progreso = fields.Float(
        string='Progreso (%)', compute='_compute_progreso', store=True,
    )
    progreso_label = fields.Char(
        string='Avance', compute='_compute_progreso', store=True,
    )
    ultima_sesion_fecha = fields.Date(
        string='Última sesión', compute='_compute_progreso', store=True,
    )
    proxima_sesion_fecha = fields.Date(
        string='Próxima sesión / retoque', compute='_compute_proxima',
        store=True,
        help='Fecha sugerida para la siguiente sesión (o el retoque si el '
             'curso ya está completo).',
    )
    proxima_es_retoque = fields.Boolean(
        compute='_compute_proxima', store=True,
    )
    alerta = fields.Selection([
        ('al_dia', 'Al día'),
        ('por_vencer', 'Por vencer'),
        ('vencida', 'Vencida'),
        ('sin_pendiente', 'Sin pendiente'),
    ], string='Estado de la próxima', compute='_compute_proxima', store=True)

    state = fields.Selection([
        ('en_curso', 'En curso'),
        ('mantenimiento', 'Mantenimiento'),
        ('completado', 'Completado'),
        ('pausado', 'Pausado'),
        ('cancelado', 'Cancelado'),
    ], string='Estado', default='en_curso', tracking=True,
        compute='_compute_state', store=True, readonly=False)

    ultimo_recordatorio = fields.Date(
        string='Último recordatorio enviado', readonly=True, copy=False,
    )
    notas = fields.Text(string='Notas')
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    color = fields.Integer(related='tipo_tratamiento_id.color', store=False)

    # ------------------------------------------------------------------

    @api.model
    def _default_doctor(self):
        emp = self.env.user.employee_id
        return emp.id if emp and emp.rol == 'doctor' else False

    @api.onchange('tipo_tratamiento_id')
    def _onchange_tipo(self):
        if self.tipo_tratamiento_id and not self.sesiones_totales:
            self.sesiones_totales = self.tipo_tratamiento_id.sesiones_recomendadas

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'in_estetica.tratamiento') or 'TRAT/0001'
            if not vals.get('sesiones_totales') and vals.get('tipo_tratamiento_id'):
                tipo = self.env['in_estetica.tipo_tratamiento'].browse(
                    vals['tipo_tratamiento_id'])
                vals['sesiones_totales'] = tipo.sesiones_recomendadas or 1
        return super().create(vals_list)

    @api.depends('sesion_ids', 'sesion_ids.state', 'sesion_ids.fecha',
                 'sesiones_totales')
    def _compute_progreso(self):
        for rec in self:
            hechas = rec.sesion_ids.filtered(lambda s: s.state == 'realizada')
            rec.sesiones_realizadas = len(hechas)
            total = rec.sesiones_totales or 0
            rec.sesiones_restantes = max(0, total - rec.sesiones_realizadas)
            rec.progreso = (rec.sesiones_realizadas / total * 100.0) if total else 0.0
            rec.progreso_label = '%d de %d' % (rec.sesiones_realizadas, total)
            fechas = hechas.mapped('fecha')
            rec.ultima_sesion_fecha = max(fechas).date() if fechas else False

    @api.depends('sesiones_realizadas', 'sesiones_totales')
    def _compute_state(self):
        for rec in self:
            if rec.state in ('pausado', 'cancelado'):
                continue
            if rec.sesiones_totales and rec.sesiones_realizadas >= rec.sesiones_totales:
                # Concluyó el total de sesiones → Completado.
                # (Si el tipo requiere retoque, el recordatorio igual se
                #  dispara por proxima_sesion_fecha aunque esté completado.)
                rec.state = 'completado'
            else:
                rec.state = 'en_curso'

    @api.depends('ultima_sesion_fecha', 'sesiones_restantes', 'fecha_inicio',
                 'state', 'tipo_tratamiento_id')
    def _compute_proxima(self):
        hoy = fields.Date.today()
        for rec in self:
            proxima = False
            es_retoque = False
            tipo = rec.tipo_tratamiento_id
            base = rec.ultima_sesion_fecha or rec.fecha_inicio
            if rec.state in ('pausado', 'cancelado'):
                proxima = False
            elif rec.sesiones_restantes > 0:
                # Siguiente sesión del curso
                if rec.ultima_sesion_fecha and tipo:
                    proxima = rec.ultima_sesion_fecha + tipo.delta_intervalo()
                else:
                    proxima = base  # aún sin sesiones: cuanto antes
            elif tipo and tipo.requiere_retoque and base:
                # Curso completo → retoque/mantenimiento
                proxima = base + tipo.delta_retoque()
                es_retoque = True
            rec.proxima_sesion_fecha = proxima
            rec.proxima_es_retoque = es_retoque
            if not proxima:
                rec.alerta = 'sin_pendiente'
            elif proxima < hoy:
                rec.alerta = 'vencida'
            elif (proxima - hoy).days <= 7:
                rec.alerta = 'por_vencer'
            else:
                rec.alerta = 'al_dia'

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_agendar_siguiente(self):
        """Abre el asistente para CONSUMIR un turno ya planificado (slot
        disponible) y reservarlo para la siguiente sesión del tratamiento.
        No crea turnos sueltos: se eligen de los generados por la planificación.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agendar sesión — %s') % self.paciente_id.name,
            'res_model': 'in_estetica.wizard_agendar_sesion',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tratamiento_id': self.id},
        }

    def action_pausar(self):
        self.write({'state': 'pausado'})

    def action_reactivar(self):
        for rec in self:
            rec.state = 'en_curso'
            rec._compute_state()

    def action_cancelar(self):
        self.write({'state': 'cancelado'})

    def action_agregar_sesiones(self):
        """Abre el asistente para sumar más sesiones a un tratamiento que
        ya se completó pero el paciente requiere continuar."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agregar más sesiones'),
            'res_model': 'in_estetica.wizard_agregar_sesiones',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tratamiento_id': self.id},
        }

    # ------------------------------------------------------------------
    # Recordatorios
    # ------------------------------------------------------------------

    def _enviar_recordatorio(self):
        """Crea una actividad interna para recepción y envía email al
        paciente recordando la próxima sesión / retoque."""
        self.ensure_one()
        # 1. Actividad interna
        responsable = (self.doctor_id.user_id or self.create_uid or self.env.user)
        tipo_act = self.env.ref('mail.mail_activity_data_todo',
                                raise_if_not_found=False)
        resumen = _('Contactar a %(pac)s: %(que)s de %(trat)s') % {
            'pac': self.paciente_id.name,
            'que': _('retoque') if self.proxima_es_retoque
                   else _('sesión %d de %d') % (self.sesiones_realizadas + 1,
                                                self.sesiones_totales),
            'trat': self.tipo_tratamiento_id.name,
        }
        if tipo_act:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=self.proxima_sesion_fecha,
                summary=resumen,
                user_id=responsable.id,
            )
        # 2. Email al paciente
        template = self.env.ref(
            'in_estetica_tratamientos.mail_template_recordatorio_sesion',
            raise_if_not_found=False,
        )
        if template and self.paciente_id.email:
            template.send_mail(self.id, force_send=False)
        self.ultimo_recordatorio = fields.Date.today()
        self.message_post(body=resumen)

    @api.model
    def _cron_recordatorios_sesiones(self, dias_anticipacion=3):
        """Detecta tratamientos cuya próxima sesión/retoque vence pronto y
        dispara los recordatorios (1 vez por ciclo)."""
        hoy = fields.Date.today()
        limite = hoy + timedelta(days=dias_anticipacion)
        candidatos = self.search([
            ('state', 'not in', ('pausado', 'cancelado')),
            ('proxima_sesion_fecha', '!=', False),
            ('proxima_sesion_fecha', '<=', limite),
        ])
        enviados = 0
        for trat in candidatos:
            # No repetir si ya se recordó después de la última sesión
            if (trat.ultimo_recordatorio and trat.ultima_sesion_fecha
                    and trat.ultimo_recordatorio > trat.ultima_sesion_fecha):
                continue
            if (trat.ultimo_recordatorio and not trat.ultima_sesion_fecha
                    and trat.ultimo_recordatorio >= trat.fecha_inicio):
                continue
            try:
                trat._enviar_recordatorio()
                enviados += 1
            except Exception:
                _logger.exception(
                    'Error enviando recordatorio del tratamiento %s', trat.name)
        if enviados:
            _logger.info('in_estetica_tratamientos: %d recordatorios enviados.',
                         enviados)
        return True
