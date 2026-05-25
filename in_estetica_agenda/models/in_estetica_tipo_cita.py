# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InNutricionTipoCita(models.Model):
    """Catálogo de tipos de cita que ofrece el consultorio.

    Cada tipo define duración (en minutos), color (para vista calendario)
    y precio referencial. La planificación de horarios genera slots según
    la duración del tipo asignado al tramo.
    """
    _name = 'in_estetica.tipo_cita'
    _description = 'Tipo de cita'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(default=10)
    duracion_min = fields.Integer(
        string='Duración (min)', required=True, default=30,
        help='Duración en minutos. Se usa para generar slots al aprobar '
             'una planificación.',
    )
    color = fields.Integer(
        string='Color', default=0,
        help='Color usado en la vista calendario de turnos.',
    )
    precio = fields.Float(
        string='Precio referencial', digits='Product Price',
        help='Tarifa sugerida. No bloquea; el cobro real se hace por fuera.',
    )
    descripcion = fields.Text(string='Descripción')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)',
         'Ya existe un tipo de cita con ese nombre.'),
    ]

    @api.constrains('duracion_min')
    def _check_duracion(self):
        for rec in self:
            if rec.duracion_min <= 0:
                raise ValidationError(_(
                    'La duración debe ser mayor a 0 minutos.'
                ))
            if rec.duracion_min > 8 * 60:
                raise ValidationError(_(
                    'La duración no puede exceder 8 horas.'
                ))
