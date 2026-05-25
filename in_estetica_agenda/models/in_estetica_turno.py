# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class InNutricionTurno(models.Model):
    """Turno / cita del consultorio.

    Estados:
      available  → slot generado, sin paciente
      reserved   → secretaria/paciente lo tomó, pendiente confirmación
      confirmed  → confirmado por la secretaria
      in_progress→ doctor inició la atención
      done       → atención finalizada
      cancelled  → cancelado en cualquier momento
    """
    _name = 'in_estetica.turno'
    _description = 'Turno'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_hora desc, id desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Referencia', readonly=True, copy=False)
    display_name = fields.Char(
        compute='_compute_display_name', store=False,
    )

    doctor_id = fields.Many2one(
        'hr.employee', string='Doctor', required=True, tracking=True,
        domain="[('rol', '=', 'doctor')]",
    )
    paciente_id = fields.Many2one(
        'in_estetica.paciente', string='Paciente', tracking=True,
        ondelete='restrict',
    )
    tipo_cita_id = fields.Many2one(
        'in_estetica.tipo_cita', string='Tipo de cita',
        help='Se asigna al reservar el turno. Los slots generados por la '
             'planificación nacen sin tipo de cita; el tipo se elige al '
             'asignar paciente.',
    )
    fecha_hora = fields.Datetime(
        string='Inicio', required=True, tracking=True,
    )
    duracion_min = fields.Integer(
        string='Duración (min)', required=True, default=30,
    )
    fecha_hora_fin = fields.Datetime(
        string='Fin', compute='_compute_fecha_hora_fin', store=True,
    )
    color = fields.Integer(
        related='tipo_cita_id.color', store=False,
        string='Color',
    )

    planificacion_id = fields.Many2one(
        'in_estetica.planificacion', string='Planificación',
        ondelete='set null', readonly=True,
    )
    state = fields.Selection([
        ('available', 'Disponible'),
        ('reserved', 'Reservado'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En curso'),
        ('done', 'Atendido'),
        ('cancelled', 'Cancelado'),
    ], default='available', required=True, tracking=True)

    notas = fields.Text(string='Notas')
    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company,
    )

    @api.depends('fecha_hora', 'duracion_min')
    def _compute_fecha_hora_fin(self):
        for rec in self:
            if rec.fecha_hora and rec.duracion_min:
                rec.fecha_hora_fin = (
                    rec.fecha_hora + timedelta(minutes=rec.duracion_min)
                )
            else:
                rec.fecha_hora_fin = False

    @api.depends('name', 'paciente_id', 'fecha_hora', 'tipo_cita_id')
    def _compute_display_name(self):
        for rec in self:
            paciente = rec.paciente_id.name or _('Sin paciente')
            fecha = (
                fields.Datetime.context_timestamp(rec, rec.fecha_hora)
                .strftime('%Y-%m-%d %H:%M')
                if rec.fecha_hora else ''
            )
            tipo = rec.tipo_cita_id.name or ''
            rec.display_name = f'{fecha} · {paciente} · {tipo}'.strip(' ·')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'in_estetica.turno'
                ) or '/'
            if 'duracion_min' not in vals and vals.get('tipo_cita_id'):
                tc = self.env['in_estetica.tipo_cita'].browse(
                    vals['tipo_cita_id']
                )
                vals['duracion_min'] = tc.duracion_min or 30
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Transiciones de estado
    # ------------------------------------------------------------------

    def action_reservar(self):
        for rec in self:
            if rec.state != 'available':
                raise UserError(_(
                    'Solo se reservan turnos disponibles.'
                ))
            if not rec.paciente_id:
                raise UserError(_(
                    'Asigna un paciente antes de reservar.'
                ))
            if not rec.tipo_cita_id:
                raise UserError(_(
                    'Asigna un tipo de cita antes de reservar.'
                ))
            rec.state = 'reserved'

    def action_confirmar(self):
        for rec in self:
            if rec.state not in ('reserved', 'available'):
                raise UserError(_(
                    'Solo se confirman turnos reservados o disponibles '
                    '(con paciente).'
                ))
            if not rec.paciente_id:
                raise UserError(_('Asigna un paciente antes de confirmar.'))
            if not rec.tipo_cita_id:
                raise UserError(_(
                    'Asigna un tipo de cita antes de confirmar.'
                ))
            rec.state = 'confirmed'

    def action_iniciar(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_(
                    'Solo se inician turnos confirmados.'
                ))
            rec.state = 'in_progress'

    def action_finalizar(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_(
                    'Solo se finalizan turnos en curso.'
                ))
            rec.state = 'done'

    def action_cancelar(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_(
                    'No se puede cancelar un turno ya atendido.'
                ))
            rec.state = 'cancelled'

    def action_liberar(self):
        """Desasigna paciente y vuelve a disponible (típico cancelación
        previa a confirmación)."""
        for rec in self:
            if rec.state in ('done', 'in_progress'):
                raise UserError(_(
                    'No se puede liberar un turno ya atendido o en curso.'
                ))
            rec.paciente_id = False
            rec.state = 'available'

    @api.constrains('fecha_hora', 'doctor_id', 'state')
    def _check_overlap(self):
        """Evita doble booking del mismo doctor en un mismo bloque."""
        for rec in self:
            if rec.state == 'cancelled' or not rec.fecha_hora:
                continue
            overlap = self.search([
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('state', '!=', 'cancelled'),
                ('fecha_hora', '<', rec.fecha_hora_fin),
                ('fecha_hora_fin', '>', rec.fecha_hora),
            ], limit=1)
            if overlap:
                raise ValidationError(_(
                    'Conflicto de horarios: el doctor %(doc)s ya tiene un '
                    'turno (%(ref)s) en ese mismo bloque.'
                ) % {'doc': rec.doctor_id.name, 'ref': overlap.name})
