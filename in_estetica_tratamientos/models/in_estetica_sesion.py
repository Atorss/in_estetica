# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class InEsteticaSesion(models.Model):
    """Una sesión (aplicación) dentro de un tratamiento.

    Normalmente se crea automáticamente al marcar un turno como atendido,
    pero también puede registrarse manualmente (walk-in).
    """
    _name = 'in_estetica.tratamiento.sesion'
    _description = 'Sesión de tratamiento'
    _order = 'fecha desc, id desc'
    _rec_name = 'display_name'

    tratamiento_id = fields.Many2one(
        'in_estetica.tratamiento', string='Tratamiento', required=True,
        ondelete='cascade', index=True,
    )
    paciente_id = fields.Many2one(
        related='tratamiento_id.paciente_id', store=True, string='Paciente',
    )
    tipo_tratamiento_id = fields.Many2one(
        related='tratamiento_id.tipo_tratamiento_id', store=True,
        string='Tipo de tratamiento',
    )
    numero = fields.Integer(string='N° de sesión', readonly=True)
    fecha = fields.Datetime(string='Fecha', default=fields.Datetime.now,
                            required=True)
    turno_id = fields.Many2one(
        'in_estetica.turno', string='Turno', ondelete='set null',
    )
    doctor_id = fields.Many2one('hr.employee', string='Médico',
                                domain="[('rol', '=', 'doctor')]")
    producto = fields.Char(string='Producto / técnica',
                           help='Producto aplicado o técnica usada en la sesión.')
    dosis = fields.Char(string='Dosis / cantidad')
    notas = fields.Text(string='Observaciones')
    state = fields.Selection([
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
    ], default='realizada', required=True, string='Estado')
    display_name = fields.Char(compute='_compute_display_name', store=True)
    company_id = fields.Many2one(
        related='tratamiento_id.company_id', store=True,
    )

    @api.depends('numero', 'tipo_tratamiento_id', 'fecha')
    def _compute_display_name(self):
        for rec in self:
            tipo = rec.tipo_tratamiento_id.name or _('Sesión')
            rec.display_name = _('%(tipo)s · sesión %(n)s') % {
                'tipo': tipo, 'n': rec.numero or '?'}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('numero') and vals.get('tratamiento_id'):
                trat = self.env['in_estetica.tratamiento'].browse(
                    vals['tratamiento_id'])
                hechas = len(trat.sesion_ids.filtered(
                    lambda s: s.state == 'realizada'))
                vals['numero'] = hechas + 1
            if not vals.get('doctor_id') and vals.get('tratamiento_id'):
                trat = self.env['in_estetica.tratamiento'].browse(
                    vals['tratamiento_id'])
                vals['doctor_id'] = trat.doctor_id.id
        return super().create(vals_list)
