# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InEsteticaTipoTratamiento(models.Model):
    """Catálogo de tipos de tratamiento de medicina estética.

    Cada tipo define cuántas sesiones se recomiendan y cada cuánto, además
    del intervalo de retoque/mantenimiento una vez completado el curso.
    Esos valores son los DEFAULTS que se proponen al crear un tratamiento
    de paciente; siempre se pueden ajustar por caso.
    """
    _name = 'in_estetica.tipo_tratamiento'
    _description = 'Tipo de tratamiento'
    _order = 'sequence, name'

    UNIDADES = [
        ('dias', 'Días'),
        ('semanas', 'Semanas'),
        ('meses', 'Meses'),
    ]

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(default=10)
    categoria = fields.Selection([
        ('facial', 'Facial'),
        ('corporal', 'Corporal'),
        ('capilar', 'Capilar'),
        ('otro', 'Otro'),
    ], string='Categoría', default='facial')

    sesiones_recomendadas = fields.Integer(
        string='Sesiones recomendadas', default=1, required=True,
        help='Número de sesiones que suele requerir el tratamiento completo.',
    )
    intervalo_valor = fields.Integer(
        string='Intervalo entre sesiones', default=2,
        help='Tiempo recomendado entre una sesión y la siguiente.',
    )
    intervalo_unidad = fields.Selection(
        UNIDADES, string='Unidad intervalo', default='semanas', required=True,
    )

    requiere_retoque = fields.Boolean(
        string='Requiere retoque/mantenimiento',
        help='Si está activo, al terminar el curso el sistema recuerda el '
             'retoque según el intervalo de retoque.',
    )
    retoque_valor = fields.Integer(string='Intervalo de retoque', default=4)
    retoque_unidad = fields.Selection(
        UNIDADES, string='Unidad retoque', default='meses', required=True,
    )

    color = fields.Integer(string='Color', default=0)
    precio = fields.Float(string='Precio referencial', digits='Product Price')
    descripcion = fields.Text(string='Descripción')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)',
         'Ya existe un tipo de tratamiento con ese nombre.'),
    ]

    @api.constrains('sesiones_recomendadas')
    def _check_sesiones(self):
        for rec in self:
            if rec.sesiones_recomendadas < 1:
                raise ValidationError(_(
                    'Las sesiones recomendadas deben ser al menos 1.'
                ))

    def _delta(self, valor, unidad):
        """Devuelve un relativedelta a partir de valor + unidad."""
        valor = max(0, valor or 0)
        if unidad == 'dias':
            return relativedelta(days=valor)
        if unidad == 'meses':
            return relativedelta(months=valor)
        return relativedelta(weeks=valor)

    def delta_intervalo(self):
        self.ensure_one()
        return self._delta(self.intervalo_valor, self.intervalo_unidad)

    def delta_retoque(self):
        self.ensure_one()
        return self._delta(self.retoque_valor, self.retoque_unidad)
