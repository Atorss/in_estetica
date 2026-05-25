# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InEsteticaTurno(models.Model):
    """Extiende el turno para vincularlo a un tratamiento y registrar la
    sesión automáticamente cuando el turno se marca como atendido."""
    _inherit = 'in_estetica.turno'

    tratamiento_id = fields.Many2one(
        'in_estetica.tratamiento', string='Tratamiento',
        help='Tratamiento al que pertenece esta cita. Al finalizar el turno '
             'se registra una sesión de este tratamiento.',
    )
    sesion_id = fields.Many2one(
        'in_estetica.tratamiento.sesion', string='Sesión registrada',
        readonly=True, copy=False,
    )

    @api.onchange('paciente_id')
    def _onchange_paciente_tratamiento(self):
        """Sugiere el tratamiento en curso del paciente, si hay uno solo."""
        if self.paciente_id and not self.tratamiento_id:
            tratos = self.env['in_estetica.tratamiento'].search([
                ('paciente_id', '=', self.paciente_id.id),
                ('state', 'in', ('en_curso', 'mantenimiento')),
            ])
            if len(tratos) == 1:
                self.tratamiento_id = tratos.id

    def _registrar_sesion(self):
        """Crea la sesión del tratamiento a partir de este turno."""
        Sesion = self.env['in_estetica.tratamiento.sesion']
        for rec in self:
            if not rec.tratamiento_id or rec.sesion_id:
                continue
            sesion = Sesion.create({
                'tratamiento_id': rec.tratamiento_id.id,
                'fecha': rec.fecha_hora or fields.Datetime.now(),
                'turno_id': rec.id,
                'doctor_id': rec.doctor_id.id,
            })
            rec.sesion_id = sesion.id

    def action_finalizar(self):
        res = super().action_finalizar()
        # Al atender el turno, si está ligado a un tratamiento, registra la sesión
        self._registrar_sesion()
        return res

    def action_registrar_sesion(self):
        """Botón manual para registrar la sesión sin cambiar el estado."""
        for rec in self:
            if not rec.tratamiento_id:
                raise UserError(_(
                    'Asigna un tratamiento al turno antes de registrar la sesión.'
                ))
        self._registrar_sesion()
        return True
