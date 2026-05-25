# -*- coding: utf-8 -*-

import logging
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

TZ = 'America/Guayaquil'


class EsteticaWebController(http.Controller):

    @http.route(['/', '/inicio'], type='http', auth='public', website=True, sitemap=True)
    def estetica_homepage(self, **kwargs):
        return request.render('in_estetica_web.estetica_homepage', {})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _tz(self):
        return pytz.timezone(TZ)

    def _now_local(self):
        return fields.Datetime.context_timestamp(
            request.env.user.sudo(), datetime.utcnow()
        )

    def _doctor_domain(self):
        # Cirujanos / medicos (rol='doctor' segun in_estetica_core)
        return [('rol', '=', 'doctor')]

    # ------------------------------------------------------------------
    # Endpoints del wizard de agendamiento
    # ------------------------------------------------------------------

    @http.route('/agendar/tipos', type='json', auth='public', website=True)
    def agendar_tipos(self, **kwargs):
        tipos = request.env['in_estetica.tipo_cita'].sudo().search(
            [('active', '=', True)], order='sequence, name'
        )
        return [{
            'id': t.id,
            'name': t.name,
            'duracion_min': t.duracion_min,
            'precio': t.precio,
            'descripcion': t.descripcion or '',
        } for t in tipos]

    @http.route('/agendar/doctores', type='json', auth='public', website=True)
    def agendar_doctores(self, **kwargs):
        doctores = request.env['hr.employee'].sudo().search(
            self._doctor_domain(), order='name'
        )
        return [{
            'id': d.id,
            'name': d.name,
            'job': d.job_title or '',
        } for d in doctores]

    @http.route('/agendar/dias-disponibles', type='json', auth='public', website=True)
    def agendar_dias_disponibles(self, doctor_id=None, tipo_cita_id=None, **kwargs):
        """Retorna fechas (YYYY-MM-DD) que tienen al menos 1 slot disponible
        en los proximos 60 dias para el doctor + tipo de cita seleccionado.
        """
        tz = self._tz()
        now_local = datetime.now(tz)
        desde_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        hasta_local = desde_local + timedelta(days=60)

        Turno = request.env['in_estetica.turno'].sudo()
        domain = [
            ('state', '=', 'available'),
            ('fecha_hora', '>=', desde_local.astimezone(pytz.UTC).replace(tzinfo=None)),
            ('fecha_hora', '<=', hasta_local.astimezone(pytz.UTC).replace(tzinfo=None)),
            ('paciente_id', '=', False),
        ]
        if doctor_id:
            domain.append(('doctor_id', '=', int(doctor_id)))

        # NOTA: no filtramos por duracion. Si el tipo necesita mas tiempo,
        # consumiremos slots contiguos al reservar.
        turnos = Turno.search(domain, order='fecha_hora asc')
        dias = set()
        for t in turnos:
            local_dt = pytz.UTC.localize(t.fecha_hora).astimezone(tz)
            # Solo futuros (descartar slots de hoy ya pasados)
            if local_dt < now_local:
                continue
            dias.add(local_dt.strftime('%Y-%m-%d'))
        return sorted(dias)

    @http.route('/agendar/slots', type='json', auth='public', website=True)
    def agendar_slots(self, doctor_id=None, tipo_cita_id=None, fecha=None, **kwargs):
        """Retorna slots disponibles del dia para doctor + tipo de cita."""
        if not fecha:
            return []
        tz = self._tz()
        try:
            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return []

        inicio_local = tz.localize(datetime.combine(fecha_obj, time.min))
        fin_local = inicio_local + timedelta(days=1)

        Turno = request.env['in_estetica.turno'].sudo()
        domain = [
            ('state', '=', 'available'),
            ('paciente_id', '=', False),
            ('fecha_hora', '>=', inicio_local.astimezone(pytz.UTC).replace(tzinfo=None)),
            ('fecha_hora', '<', fin_local.astimezone(pytz.UTC).replace(tzinfo=None)),
        ]
        if doctor_id:
            domain.append(('doctor_id', '=', int(doctor_id)))

        # No filtramos por duracion: si el tipo necesita mas, consumiremos
        # slots contiguos al reservar.
        now_local = datetime.now(tz)
        turnos = Turno.search(domain, order='fecha_hora asc')
        slots = []
        for t in turnos:
            local_dt = pytz.UTC.localize(t.fecha_hora).astimezone(tz)
            if local_dt < now_local:
                continue
            slots.append({
                'id': t.id,
                'hora': local_dt.strftime('%H:%M'),
                'doctor_id': t.doctor_id.id,
                'doctor_name': t.doctor_id.name,
                'duracion_min': t.duracion_min,
            })
        return slots

    @http.route('/agendar/buscar-paciente', type='json', auth='public', website=True)
    def agendar_buscar_paciente(self, cedula=None, **kwargs):
        """Si existe un paciente con esa cedula (vat), devuelve sus datos
        para autocompletar el formulario."""
        cedula = (cedula or '').strip()
        if not cedula or not re.match(r'^\d{8,15}$', cedula):
            return {'found': False}
        paciente = request.env['in_estetica.paciente'].sudo().search(
            [('vat', '=', cedula)], limit=1
        )
        if not paciente:
            return {'found': False}
        # Separar nombre / apellido: ultima palabra(s) como apellido
        full = (paciente.name or '').strip()
        parts = full.split()
        if len(parts) >= 2:
            mid = len(parts) // 2
            nombre = ' '.join(parts[:mid]) or parts[0]
            apellido = ' '.join(parts[mid:]) or ''
        else:
            nombre = full
            apellido = ''
        return {
            'found': True,
            'nombre': nombre,
            'apellido': apellido,
            'email': paciente.email or '',
            'telefono': paciente.phone or paciente.mobile or '',
        }

    @http.route('/agendar/reservar', type='json', auth='public', website=True)
    def agendar_reservar(self, **post):
        """Crea/busca paciente, asigna al turno y lo deja en reservado."""
        try:
            turno_id = int(post.get('turno_id') or 0)
            tipo_cita_id = int(post.get('tipo_cita_id') or 0)
            cedula = (post.get('cedula') or '').strip()
            nombre = (post.get('nombre') or '').strip()
            apellido = (post.get('apellido') or '').strip()
            email = (post.get('email') or '').strip()
            telefono = (post.get('telefono') or '').strip()
            notas = (post.get('notas') or '').strip()

            if not all([turno_id, tipo_cita_id, cedula, nombre, apellido, email, telefono]):
                return {'success': False, 'message': 'Faltan datos obligatorios.'}

            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                return {'success': False, 'message': 'Email invalido.'}

            if not re.match(r'^\d{8,15}$', cedula):
                return {'success': False, 'message': 'Cedula invalida (solo numeros, 8-15 digitos).'}

            Turno = request.env['in_estetica.turno'].sudo()
            turno = Turno.browse(turno_id)
            if not turno.exists():
                return {'success': False, 'message': 'El turno ya no existe.'}
            if turno.state != 'available' or turno.paciente_id:
                return {'success': False, 'message': 'Este horario ya fue tomado por otra persona. Elige otro.'}

            Tipo = request.env['in_estetica.tipo_cita'].sudo().browse(tipo_cita_id)
            if not Tipo.exists():
                return {'success': False, 'message': 'Tipo de cita no encontrado.'}

            # Buscar paciente por VAT (cedula) o crear uno nuevo.
            # in_estetica.paciente delega via _inherits a res.partner: los
            # campos name/vat/email/phone se persisten en el partner asociado.
            Paciente = request.env['in_estetica.paciente'].sudo()
            paciente = Paciente.search([('vat', '=', cedula)], limit=1)
            full_name = f'{nombre} {apellido}'.strip()
            vals = {
                'name': full_name,
                'vat': cedula,
                'email': email,
                'phone': telefono,
            }
            if paciente:
                paciente.write({k: v for k, v in vals.items() if v})
            else:
                paciente = Paciente.create(vals)

            # Asignar paciente y tipo. La duracion del slot se mantiene
            # tal como vino de la planificacion; el doctor ajustara en la
            # consulta si la atencion se extiende.
            turno.write({
                'paciente_id': paciente.id,
                'tipo_cita_id': tipo_cita_id,
                'notas': notas,
            })
            turno.action_reservar()

            tz = self._tz()
            local_dt = pytz.UTC.localize(turno.fecha_hora).astimezone(tz)
            return {
                'success': True,
                'message': 'Reserva confirmada. Te contactaremos para confirmar.',
                'ref': turno.name,
                'fecha': local_dt.strftime('%d/%m/%Y'),
                'hora': local_dt.strftime('%H:%M'),
                'doctor': turno.doctor_id.name,
                'tipo': Tipo.name,
            }
        except Exception:
            _logger.exception('Error reservando turno desde web')
            return {'success': False, 'message': 'Ocurrio un error. Intenta nuevamente.'}
