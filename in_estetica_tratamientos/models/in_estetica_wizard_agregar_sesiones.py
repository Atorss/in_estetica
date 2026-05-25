# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardAgregarSesiones(models.TransientModel):
    """Suma sesiones a un tratamiento (cuando el paciente requiere continuar
    después de haber completado el total previsto)."""
    _name = 'in_estetica.wizard_agregar_sesiones'
    _description = 'Agregar más sesiones'

    tratamiento_id = fields.Many2one(
        'in_estetica.tratamiento', string='Tratamiento', required=True,
    )
    progreso_actual = fields.Char(
        related='tratamiento_id.progreso_label', string='Sesiones actuales',
        readonly=True,
    )
    cantidad = fields.Integer(string='Sesiones a agregar', default=1, required=True)

    def action_confirmar(self):
        self.ensure_one()
        if self.cantidad <= 0:
            raise UserError(_('Indica cuántas sesiones agregar (mayor a 0).'))
        nuevo_total = (self.tratamiento_id.sesiones_totales or 0) + self.cantidad
        self.tratamiento_id.write({'sesiones_totales': nuevo_total})
        self.tratamiento_id.message_post(body=_(
            'Se agregaron %(n)d sesión(es). Nuevo total: %(t)d.'
        ) % {'n': self.cantidad, 't': nuevo_total})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'in_estetica.tratamiento',
            'res_id': self.tratamiento_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
