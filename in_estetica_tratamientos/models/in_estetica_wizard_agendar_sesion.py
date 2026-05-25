# -*- coding: utf-8 -*-

import pytz

from odoo import models, fields, api, _
from odoo.exceptions import UserError

TZ_DEFAULT = 'America/Guayaquil'


class WizardAgendarSesion(models.TransientModel):
    """Asistente para agendar la siguiente sesión de un tratamiento
    CONSUMIENDO un turno ya planificado. Primero se filtra por una fecha
    (solo se ofrecen las fechas que tienen turnos libres) y luego se elige
    el horario de ese día."""
    _name = 'in_estetica.wizard_agendar_sesion'
    _description = 'Agendar siguiente sesión'

    tratamiento_id = fields.Many2one(
        'in_estetica.tratamiento', string='Tratamiento', required=True,
    )
    paciente_id = fields.Many2one(
        related='tratamiento_id.paciente_id', string='Paciente', readonly=True,
    )
    doctor_id = fields.Many2one(
        'hr.employee', string='Médico', readonly=True,
        help='Médico del tratamiento. Los turnos se filtran por este médico.',
    )
    proxima_tentativa = fields.Date(
        related='tratamiento_id.proxima_sesion_fecha', readonly=True,
        string='Próxima sesión sugerida',
    )
    tipo_cita_id = fields.Many2one(
        'in_estetica.tipo_cita', string='Tipo de cita', required=True,
    )
    fecha = fields.Selection(
        selection='_get_fechas_disponibles', string='Fecha', required=True,
        help='Solo se muestran las fechas que tienen turnos libres.',
    )
    turno_id = fields.Many2one(
        'in_estetica.turno', string='Horario disponible', required=True,
        help='Turnos libres del día seleccionado.',
    )
    turno_domain = fields.Char(compute='_compute_turno_domain')
    sin_disponibilidad = fields.Boolean(compute='_compute_turno_domain')

    # ------------------------------------------------------------------

    def _tz(self):
        return pytz.timezone(self.env.user.tz or TZ_DEFAULT)

    def _slots_disponibles(self, doctor):
        """Turnos available (sin paciente) futuros, del médico dado."""
        domain = [
            ('state', '=', 'available'),
            ('paciente_id', '=', False),
            ('fecha_hora', '>=', fields.Datetime.now()),
        ]
        if doctor:
            domain.append(('doctor_id', '=', doctor.id))
        return self.env['in_estetica.turno'].search(domain, order='fecha_hora')

    @api.model
    def _get_fechas_disponibles(self):
        """Opciones del selector de fecha = días (locales) con turnos libres."""
        trat_id = self.env.context.get('default_tratamiento_id')
        doctor = False
        if trat_id:
            doctor = self.env['in_estetica.tratamiento'].browse(trat_id).doctor_id
        tz = self._tz()
        fechas = {}
        for t in self._slots_disponibles(doctor):
            local = pytz.UTC.localize(t.fecha_hora).astimezone(tz)
            key = local.strftime('%Y-%m-%d')
            if key not in fechas:
                fechas[key] = local.strftime('%a %d/%m/%Y')
        return [(k, fechas[k]) for k in sorted(fechas)]

    @api.depends('fecha', 'doctor_id')
    def _compute_turno_domain(self):
        tz = self._tz()
        for w in self:
            ids = []
            if w.fecha:
                for t in self._slots_disponibles(w.doctor_id):
                    local = pytz.UTC.localize(t.fecha_hora).astimezone(tz)
                    if local.strftime('%Y-%m-%d') == w.fecha:
                        ids.append(t.id)
            w.turno_domain = str([('id', 'in', ids)])
            w.sin_disponibilidad = not bool(w._get_fechas_disponibles())

    @api.onchange('fecha')
    def _onchange_fecha(self):
        # al cambiar la fecha, limpiar el turno elegido (era de otro día)
        self.turno_id = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        trat_id = self.env.context.get('default_tratamiento_id')
        if not trat_id:
            return res
        trat = self.env['in_estetica.tratamiento'].browse(trat_id)
        res.setdefault('tratamiento_id', trat.id)
        if trat.doctor_id:
            res.setdefault('doctor_id', trat.doctor_id.id)
        tipo = self.env.ref(
            'in_estetica_agenda.tipo_cita_control', raise_if_not_found=False,
        )
        if tipo:
            res.setdefault('tipo_cita_id', tipo.id)
        # Fecha por defecto: la primera fecha disponible >= próxima sugerida;
        # si no hay, la primera disponible.
        opciones = [k for k, _l in self._get_fechas_disponibles()]
        if opciones:
            prox = trat.proxima_sesion_fecha
            elegida = None
            if prox:
                prox_str = fields.Date.to_string(prox)
                posteriores = [o for o in opciones if o >= prox_str]
                elegida = posteriores[0] if posteriores else None
            res.setdefault('fecha', elegida or opciones[0])
        return res

    def action_confirmar(self):
        self.ensure_one()
        turno = self.turno_id
        if turno.state != 'available' or turno.paciente_id:
            raise UserError(_(
                'Ese turno ya fue tomado. Elige otro horario disponible.'
            ))
        turno.write({
            'paciente_id': self.paciente_id.id,
            'tratamiento_id': self.tratamiento_id.id,
            'tipo_cita_id': self.tipo_cita_id.id,
        })
        turno.action_reservar()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Turno reservado'),
            'res_model': 'in_estetica.turno',
            'res_id': turno.id,
            'view_mode': 'form',
            'target': 'current',
        }
