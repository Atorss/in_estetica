# -*- coding: utf-8 -*-
"""Gate del motor IA por saldo de recargas de la suscripción.

El motor genérico (innatum.ai.engine) ya tiene un gate por límite mensual
y por conversación. Acá agregamos un chequeo previo: si la company actual
tiene una suscripción in_estetica_control y su saldo de recargas IA es 0, bloqueamos
la llamada con un mensaje útil para el operador.

Si in_estetica_control NO está instalado, este hook no existe y el motor genérico
funciona sin cambios.
"""

import logging

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIEngineExtension(models.AbstractModel):
    _inherit = 'innatum.ai.engine'

    @api.model
    def _is_chatbot_available_for_company(self, company):
        """Override: solo si la company tiene saldo IA disponible."""
        Sus = self.env['in_estetica_control.suscripcion'].sudo()
        return Sus._has_ai_credit_for_company(company)

    def _check_cost_limits(self, provider, conversation=None):
        # 1. Chequeo estándar del engine (límite mensual + conversación)
        super()._check_cost_limits(provider, conversation=conversation)

        # 2. Gate por suscripción in_estetica_control.
        # IMPORTANTE: NO chequear self.env.user.has_group(...) porque los
        # controllers públicos llaman con sudo() y self.env.user pasa a
        # ser admin, lo que bypaseaba el gate para tenants reales.
        company = self.env.company
        if not company:
            return

        Sus = self.env['in_estetica_control.suscripcion'].sudo()
        susc = Sus._get_active_for_company(company)
        if not susc:
            # Sin suscripción para esta company: caller técnico o
            # testing interno de Innatum. No se bloquea para no romper
            # pruebas, pero se loguea.
            _logger.info(
                'AI gate: company %s (id=%s) sin suscripción activa — bypass.',
                company.name, company.id,
            )
            return

        if not susc.recarga_ids:
            raise UserError(_(
                'No tienes recargas IA activas. Contacta a Innatum para '
                'cargar saldo y empezar a usar las funciones de IA.'
            ))

        if susc.tokens_restantes_total_usd <= 0:
            _logger.info(
                'AI gate: company %s sin saldo (recargas=%s, restante=%.4f)',
                company.name, len(susc.recarga_ids),
                susc.tokens_restantes_total_usd,
            )
            raise UserError(_(
                'Sin saldo de IA disponible. Las recargas se agotaron. '
                'Contacta a Innatum para recargar tu saldo.'
            ))
