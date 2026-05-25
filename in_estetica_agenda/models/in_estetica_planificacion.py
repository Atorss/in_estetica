# -*- coding: utf-8 -*-

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


# (weekday Python: 0=Lun ... 6=Dom, field_name, label corto)
DAY_FIELDS = [
    (0, 'lunes', 'Lun'),
    (1, 'martes', 'Mar'),
    (2, 'miercoles', 'Mié'),
    (3, 'jueves', 'Jue'),
    (4, 'viernes', 'Vie'),
    (5, 'sabado', 'Sáb'),
    (6, 'domingo', 'Dom'),
]
DAY_LABELS = {wd: lab for wd, _f, lab in DAY_FIELDS}


class InNutricionPlanificacion(models.Model):
    """Planificación de horarios de atención del doctor.

    Define un rango de fechas y una grilla de tramos. Cada tramo (línea)
    representa una franja "X días de la semana, de hora_inicio a hora_fin".
    Al aprobar, se generan slots `available` cada `duracion_turno` minutos.

    Nota de diseño: la duración del turno vive a nivel planificación (no
    de tramo ni de tipo de cita). El tipo de cita se decide al asignar el
    paciente al turno, no al planificar.
    """
    _name = 'in_estetica.planificacion'
    _description = 'Planificación de horarios'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_inicio desc, id desc'

    name = fields.Char(
        string='Referencia', readonly=True, copy=False, default='Nueva',
    )
    doctor_id = fields.Many2one(
        'hr.employee', string='Doctor', required=True, tracking=True,
        domain="[('rol', '=', 'doctor'), ('active', '=', True)]",
        default=lambda self: self._default_doctor(),
    )
    fecha_inicio = fields.Date(
        string='Desde', required=True, tracking=True,
        default=fields.Date.today,
    )
    fecha_fin = fields.Date(
        string='Hasta', required=True, tracking=True,
    )
    duracion_turno = fields.Integer(
        string='Duración turno (min)', required=True, default=30,
        tracking=True,
        help='Duración de cada slot generado, en minutos. Aplica a todos '
             'los tramos de esta planificación.',
    )
    linea_ids = fields.One2many(
        'in_estetica.planificacion.linea', 'planificacion_id',
        string='Tramos',
    )
    turno_ids = fields.One2many(
        'in_estetica.turno', 'planificacion_id',
        string='Turnos generados',
    )
    turno_count = fields.Integer(
        compute='_compute_turno_count', string='# Turnos',
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('approved', 'Aprobada'),
        ('cancelled', 'Cancelada'),
    ], default='draft', required=True, tracking=True)
    notas = fields.Text(string='Notas')
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def _default_doctor(self):
        emp = self.env.user.employee_id
        if emp and emp.rol == 'doctor':
            return emp.id
        return False

    @api.depends('turno_ids')
    def _compute_turno_count(self):
        for rec in self:
            rec.turno_count = len(rec.turno_ids)

    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        for rec in self:
            if rec.fecha_fin < rec.fecha_inicio:
                raise ValidationError(_(
                    'La fecha "Hasta" debe ser mayor o igual a "Desde".'
                ))

    @api.constrains('duracion_turno')
    def _check_duracion(self):
        for rec in self:
            if rec.duracion_turno <= 0:
                raise ValidationError(_(
                    'La duración del turno debe ser mayor a 0 minutos.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'in_estetica.planificacion'
                ) or 'PLAN/0001'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_aprobar(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Solo se pueden aprobar planificaciones en borrador.'
                ))
            if not rec.linea_ids:
                raise UserError(_(
                    'Agrega al menos un tramo antes de aprobar.'
                ))
            rec._generar_turnos()
            rec.state = 'approved'

    def action_cancelar(self):
        """Cancela la planificación y los turnos `available` asociados.

        Turnos reservados/confirmados/atendidos NO se tocan.
        """
        for rec in self:
            disponibles = rec.turno_ids.filtered(
                lambda t: t.state == 'available',
            )
            disponibles.write({'state': 'cancelled'})
            rec.state = 'cancelled'

    def action_volver_a_borrador(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_(
                    'Solo se puede revertir a borrador desde el estado '
                    '"Cancelada".'
                ))
            rec.state = 'draft'

    def action_ver_turnos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Turnos de %s') % self.name,
            'res_model': 'in_estetica.turno',
            'view_mode': 'list,calendar,form',
            'domain': [('planificacion_id', '=', self.id)],
            'context': {'default_planificacion_id': self.id},
        }

    # ------------------------------------------------------------------
    # Generación de slots
    # ------------------------------------------------------------------

    def _generar_turnos(self):
        """Itera el rango de fechas y crea un turno por slot.

        Para cada fecha del rango, busca todas las líneas activas en ese
        día de la semana, y dentro de cada línea genera bloques de
        `duracion_turno` minutos entre `hora_inicio` y `hora_fin`.

        Maneja timezone: horas locales del usuario → UTC para guardar.
        """
        self.ensure_one()
        # sudo: la generación de slots es una operación interna disparada al
        # aprobar la planificación. El permiso ya está validado por quien
        # aprueba; un médico puede aprobar su planificación aunque no tenga
        # permiso directo para crear turnos sueltos.
        Turno = self.env['in_estetica.turno'].sudo()

        tz_name = self.env.user.tz or self.company_id.partner_id.tz or 'UTC'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.UTC

        paso = self.duracion_turno  # minutos

        # Index líneas por weekday → [lineas que aplican]
        lineas_por_dow = {}
        for linea in self.linea_ids:
            for dow in linea._get_dias_activos():
                lineas_por_dow.setdefault(dow, []).append(linea)

        turnos_vals = []
        fecha = self.fecha_inicio
        while fecha <= self.fecha_fin:
            dow = fecha.weekday()
            for linea in lineas_por_dow.get(dow, []):
                h_ini = int(linea.hora_inicio)
                m_ini = int(round((linea.hora_inicio - h_ini) * 60))
                h_fin = int(linea.hora_fin)
                m_fin = int(round((linea.hora_fin - h_fin) * 60))
                dt_ini = tz.localize(
                    datetime.combine(fecha, time(h_ini, m_ini))
                )
                dt_fin = tz.localize(
                    datetime.combine(fecha, time(h_fin, m_fin))
                )
                cursor = dt_ini
                while cursor + timedelta(minutes=paso) <= dt_fin:
                    dt_utc = cursor.astimezone(pytz.UTC).replace(tzinfo=None)
                    turnos_vals.append({
                        'doctor_id': self.doctor_id.id,
                        'planificacion_id': self.id,
                        'fecha_hora': dt_utc,
                        'duracion_min': paso,
                        'state': 'available',
                        'company_id': self.company_id.id,
                    })
                    cursor += timedelta(minutes=paso)
            fecha += timedelta(days=1)

        if turnos_vals:
            Turno.create(turnos_vals)
            _logger.info(
                'in_estetica_agenda: planificacion %s generó %d turnos.',
                self.name, len(turnos_vals),
            )


class InNutricionPlanificacionLinea(models.Model):
    """Tramo de una planificación: 1..7 días con un mismo horario.

    Una línea = "los días marcados, de hora_inicio a hora_fin". El detalle
    de qué tipo de cita ocupa cada slot se define al reservar el turno,
    NO acá.
    """
    _name = 'in_estetica.planificacion.linea'
    _description = 'Tramo de planificación'
    _order = 'planificacion_id, hora_inicio'

    planificacion_id = fields.Many2one(
        'in_estetica.planificacion', required=True, ondelete='cascade',
    )
    # 7 booleanos, uno por día de la semana
    lunes = fields.Boolean(string='Lun')
    martes = fields.Boolean(string='Mar')
    miercoles = fields.Boolean(string='Mié')
    jueves = fields.Boolean(string='Jue')
    viernes = fields.Boolean(string='Vie')
    sabado = fields.Boolean(string='Sáb')
    domingo = fields.Boolean(string='Dom')

    hora_inicio = fields.Float(
        string='Desde', required=True, default=8.0,
        help='Hora de inicio (24h, decimal: 8.5 = 8:30).',
    )
    hora_fin = fields.Float(
        string='Hasta', required=True, default=12.0,
    )
    dias_display = fields.Char(
        string='Días', compute='_compute_dias_display',
    )
    turnos_por_dia = fields.Integer(
        string='Turnos / día', compute='_compute_turnos_por_dia',
    )

    def _get_dias_activos(self):
        """Lista de weekday Python (0..6) marcados en esta línea."""
        self.ensure_one()
        return [wd for wd, fname, _l in DAY_FIELDS if self[fname]]

    @api.depends('lunes', 'martes', 'miercoles', 'jueves', 'viernes',
                 'sabado', 'domingo')
    def _compute_dias_display(self):
        for rec in self:
            etiquetas = [
                lab for wd, fname, lab in DAY_FIELDS if rec[fname]
            ]
            rec.dias_display = ', '.join(etiquetas) if etiquetas else ''

    @api.depends('hora_inicio', 'hora_fin',
                 'planificacion_id.duracion_turno')
    def _compute_turnos_por_dia(self):
        for rec in self:
            duracion = rec.planificacion_id.duracion_turno or 0
            if duracion > 0:
                rec.turnos_por_dia = int(
                    (rec.hora_fin - rec.hora_inicio) * 60 / duracion
                )
            else:
                rec.turnos_por_dia = 0

    @api.constrains('hora_inicio', 'hora_fin')
    def _check_horas(self):
        for rec in self:
            if not (0 <= rec.hora_inicio < 24):
                raise ValidationError(_(
                    'Hora "Desde" inválida (entre 0 y 24).'
                ))
            if not (0 < rec.hora_fin <= 24):
                raise ValidationError(_(
                    'Hora "Hasta" inválida (entre 0 y 24).'
                ))
            if rec.hora_fin <= rec.hora_inicio:
                raise ValidationError(_(
                    'La hora "Hasta" debe ser mayor que "Desde".'
                ))

    @api.constrains('lunes', 'martes', 'miercoles', 'jueves', 'viernes',
                    'sabado', 'domingo')
    def _check_al_menos_un_dia(self):
        for rec in self:
            if not rec._get_dias_activos():
                raise ValidationError(_(
                    'Marca al menos un día de la semana en el tramo.'
                ))

    @api.constrains('hora_inicio', 'hora_fin', 'lunes', 'martes', 'miercoles',
                    'jueves', 'viernes', 'sabado', 'domingo', 'planificacion_id')
    def _check_no_overlap(self):
        """Rechaza dos tramos de la misma planificación que se solapen
        en algún día compartido."""
        for rec in self:
            dias = set(rec._get_dias_activos())
            for otra in (rec.planificacion_id.linea_ids - rec):
                dias_comunes = dias & set(otra._get_dias_activos())
                if not dias_comunes:
                    continue
                if rec.hora_inicio < otra.hora_fin \
                        and rec.hora_fin > otra.hora_inicio:
                    nombres = ', '.join(
                        DAY_LABELS[d] for d in sorted(dias_comunes)
                    )
                    raise ValidationError(_(
                        'Solapamiento de tramos en %(dias)s: '
                        '%(ini1)02d:%(min1)02d-%(fin1)02d:%(fmin1)02d '
                        'vs %(ini2)02d:%(min2)02d-%(fin2)02d:%(fmin2)02d.'
                    ) % {
                        'dias': nombres,
                        'ini1': int(rec.hora_inicio),
                        'min1': int((rec.hora_inicio % 1) * 60),
                        'fin1': int(rec.hora_fin),
                        'fmin1': int((rec.hora_fin % 1) * 60),
                        'ini2': int(otra.hora_inicio),
                        'min2': int((otra.hora_inicio % 1) * 60),
                        'fin2': int(otra.hora_fin),
                        'fmin2': int((otra.hora_fin % 1) * 60),
                    })
