# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class InControlRecargaIA(models.Model):
    """Recarga de saldo IA sobre una suscripción.

    Cada recarga es un cobro al cliente. El consumo se imputa FIFO contra
    las recargas de la suscripción, ordenadas por fecha. El margen se
    snapshotea al crear: cambios posteriores al ai_margin_pct de la
    suscripción NO afectan recargas existentes.

    Fórmulas:
      tokens_disponibles_usd = monto_cobrado_usd × (1 - margen_pct/100)
      tokens_consumidos_usd  = sum(ai.usage.log.cost_usd) desde la fecha
                               de la PRIMERA recarga, imputado FIFO
      tokens_restantes_usd   = disponibles - consumidos
    """
    _name = 'in_estetica_control.recarga_ia'
    _description = 'Recarga de saldo IA'
    _order = 'fecha desc, id desc'
    _rec_name = 'display_name'

    suscripcion_id = fields.Many2one(
        'in_estetica_control.suscripcion', string='Suscripción',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        related='suscripcion_id.company_id', store=True, readonly=True,
        string='Empresa', index=True,
    )
    fecha = fields.Date(
        string='Fecha', required=True, default=fields.Date.today,
        help='Fecha del cobro. El consumo desde esta fecha cuenta contra '
             'el saldo de la suscripción.',
    )
    monto_cobrado_usd = fields.Float(
        string='Monto cobrado (USD)', required=True, digits=(12, 4),
        help='Lo que pagó el cliente por esta recarga.',
    )
    margen_pct_aplicado = fields.Float(
        string='Margen aplicado (%)', required=True, digits=(5, 2),
        readonly=True,
        help='Snapshot del margen IA de la suscripción al crear la recarga.',
    )
    tokens_disponibles_usd = fields.Float(
        string='Disponible (USD)',
        compute='_compute_tokens', store=True, digits=(12, 4),
        help='monto × (1 - margen%) — saldo neto consumible.',
    )
    tokens_consumidos_usd = fields.Float(
        string='Consumido (USD)',
        compute='_compute_tokens', digits=(12, 4), store=False,
    )
    tokens_restantes_usd = fields.Float(
        string='Restante (USD)',
        compute='_compute_tokens', digits=(12, 4), store=False,
    )
    state = fields.Selection([
        ('vigente', 'Vigente'),
        ('agotada', 'Agotada'),
    ], string='Estado', compute='_compute_tokens', store=False)

    # Vista cliente (sin revelar margen)
    consumido_visible_usd = fields.Float(
        string='Consumido (vista cliente)',
        compute='_compute_tokens', digits=(12, 4), store=False,
        help='Consumo proporcional al monto cobrado.',
    )
    restante_visible_usd = fields.Float(
        string='Restante (vista cliente)',
        compute='_compute_tokens', digits=(12, 4), store=False,
    )

    notes = fields.Text(string='Notas')
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('fecha', 'monto_cobrado_usd')
    def _compute_display_name(self):
        for rec in self:
            if rec.fecha and rec.monto_cobrado_usd:
                rec.display_name = (
                    f'Recarga {rec.fecha} — ${rec.monto_cobrado_usd:.2f}'
                )
            else:
                rec.display_name = _('Nueva recarga')

    @api.depends('monto_cobrado_usd', 'margen_pct_aplicado', 'fecha',
                 'suscripcion_id', 'company_id')
    def _compute_tokens(self):
        """Calcula consumido/restante con imputación FIFO por suscripción.

        Por cada suscripción tocada por `self`:
          1. Ordena sus recargas por fecha asc, id asc
          2. Suma todos los ai.usage.log.cost_usd de la company desde la
             primera recarga
          3. Imputa ese consumo total FIFO sobre las recargas hasta agotar
        """
        UsageLog = self.env.get('innatum.ai.usage.log')

        # 1. Disponibles siempre
        for rec in self:
            factor = max(0.0, 1.0 - (rec.margen_pct_aplicado or 0.0) / 100.0)
            rec.tokens_disponibles_usd = (rec.monto_cobrado_usd or 0.0) * factor

        # 2. Sin motor IA instalado: todo vigente, 0 consumo
        if UsageLog is None:
            for rec in self:
                rec.tokens_consumidos_usd = 0.0
                rec.tokens_restantes_usd = rec.tokens_disponibles_usd
                rec.consumido_visible_usd = 0.0
                rec.restante_visible_usd = rec.monto_cobrado_usd or 0.0
                rec.state = 'vigente' if rec.tokens_disponibles_usd > 0 else 'agotada'
            return

        # 3. Agrupar por suscripción
        suscripciones = {}
        for rec in self:
            if rec.suscripcion_id.id:
                suscripciones.setdefault(
                    rec.suscripcion_id.id, self.env[self._name],
                )
                suscripciones[rec.suscripcion_id.id] |= rec

        UsageLog = UsageLog.sudo()
        procesadas = self.env[self._name]

        for sus_id, _recs in suscripciones.items():
            todas = self.sudo().search(
                [('suscripcion_id', '=', sus_id)],
                order='fecha asc, id asc',
            )
            if not todas:
                continue
            # Disponibles para las que no están en self
            for r in todas:
                if r.id not in self.ids:
                    factor = max(
                        0.0, 1.0 - (r.margen_pct_aplicado or 0.0) / 100.0,
                    )
                    r.tokens_disponibles_usd = (
                        (r.monto_cobrado_usd or 0.0) * factor
                    )

            company = todas[0].company_id
            primera_fecha = todas[0].fecha
            if not company or not primera_fecha:
                for r in todas:
                    r.tokens_consumidos_usd = 0.0
                    r.tokens_restantes_usd = r.tokens_disponibles_usd
                    r.consumido_visible_usd = 0.0
                    r.restante_visible_usd = r.monto_cobrado_usd or 0.0
                    r.state = (
                        'vigente' if r.tokens_disponibles_usd > 0
                        else 'agotada'
                    )
                    procesadas |= r
                continue

            fecha_dt = fields.Datetime.to_string(
                datetime.combine(primera_fecha, datetime.min.time())
            )
            logs = UsageLog.search([
                ('company_id', '=', company.id),
                ('create_date', '>=', fecha_dt),
            ])
            consumo_total = sum(logs.mapped('cost_usd'))

            remaining = consumo_total
            for r in todas:
                disp = r.tokens_disponibles_usd or 0.0
                consumido = min(remaining, disp)
                r.tokens_consumidos_usd = consumido
                r.tokens_restantes_usd = max(0.0, disp - consumido)
                cobrado = r.monto_cobrado_usd or 0.0
                if disp > 0:
                    pct = consumido / disp
                    r.consumido_visible_usd = pct * cobrado
                    r.restante_visible_usd = max(
                        0.0, cobrado - r.consumido_visible_usd,
                    )
                else:
                    r.consumido_visible_usd = 0.0
                    r.restante_visible_usd = cobrado
                r.state = 'vigente' if r.tokens_restantes_usd > 0 else 'agotada'
                remaining -= consumido
                procesadas |= r

        # 4. Defensivo: recargas sin suscripción
        for rec in self - procesadas:
            rec.tokens_consumidos_usd = 0.0
            rec.tokens_restantes_usd = rec.tokens_disponibles_usd
            rec.consumido_visible_usd = 0.0
            rec.restante_visible_usd = rec.monto_cobrado_usd or 0.0
            rec.state = (
                'vigente' if rec.tokens_disponibles_usd > 0 else 'agotada'
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Snapshot del margen vigente de la suscripción al crear.

        Valida también que exista al menos un proveedor IA activo: cargar
        saldo sin proveedor configurado no tiene sentido operativo y
        bloquearlo acá evita recargas que luego no se pueden consumir.
        """
        Provider = self.env['innatum.ai.provider'].sudo()
        if not Provider.search_count([('active', '=', True)]):
            raise ValidationError(_(
                'No hay ningún proveedor IA activo configurado. '
                'Configure un proveedor (Claude, OpenAI o Gemini) en '
                'Innatum AI > Proveedores antes de cargar recargas.'
            ))
        Sus = self.env['in_estetica_control.suscripcion'].sudo()
        for vals in vals_list:
            if 'margen_pct_aplicado' not in vals and vals.get('suscripcion_id'):
                sus = Sus.browse(vals['suscripcion_id'])
                vals['margen_pct_aplicado'] = sus.ai_margin_pct or 0.0
        return super().create(vals_list)

    @api.constrains('monto_cobrado_usd')
    def _check_monto_positivo(self):
        for rec in self:
            if rec.monto_cobrado_usd <= 0:
                raise ValidationError(_(
                    'El monto cobrado debe ser mayor a 0.'
                ))

    @api.constrains('margen_pct_aplicado')
    def _check_margin(self):
        for rec in self:
            if not (0 <= rec.margen_pct_aplicado <= 100):
                raise ValidationError(_(
                    'El margen aplicado debe estar entre 0 y 100%.'
                ))
