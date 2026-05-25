# -*- coding: utf-8 -*-

import logging
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


GENERO_SELECTION = [
    ('femenino', 'Femenino'),
    ('masculino', 'Masculino'),
    ('otro', 'Otro'),
]

ESTADO_CIVIL_SELECTION = [
    ('soltero', 'Soltero/a'),
    ('casado', 'Casado/a'),
    ('union_libre', 'Unión libre'),
    ('divorciado', 'Divorciado/a'),
    ('viudo', 'Viudo/a'),
]

# Escala de fototipo de Fitzpatrick — relevante para láser y tratamientos
FOTOTIPO_SELECTION = [
    ('I', 'I — Muy clara'),
    ('II', 'II — Clara'),
    ('III', 'III — Media'),
    ('IV', 'IV — Morena clara'),
    ('V', 'V — Morena oscura'),
    ('VI', 'VI — Muy oscura'),
]


class InEsteticaPaciente(models.Model):
    """Paciente del centro de medicina estética.

    Herencia por delegación sobre res.partner: cada paciente persiste su
    propia fila y delega los campos demográficos (name, vat, phone, email,
    dirección…) en un res.partner asociado. Así mantenemos vistas y permisos
    propios sin contaminar res.partner.
    """
    _name = 'in_estetica.paciente'
    _description = 'Paciente'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    partner_id = fields.Many2one(
        'res.partner', string='Contacto base', required=True,
        ondelete='restrict', auto_join=True,
        help='Registro de res.partner que respalda al paciente. Se crea '
             'automáticamente; al borrar el paciente se borra también.',
    )
    ref_paciente = fields.Char(
        string='Código', readonly=True, copy=False, index=True,
        default=lambda self: _('Nuevo'),
    )

    # --- Datos personales ---
    fecha_nacimiento = fields.Date(string='Fecha de nacimiento', tracking=True)
    edad = fields.Integer(string='Edad', compute='_compute_edad', store=False)
    genero = fields.Selection(GENERO_SELECTION, string='Género', tracking=True)
    estado_civil = fields.Selection(ESTADO_CIVIL_SELECTION, string='Estado civil')
    ocupacion = fields.Char(string='Ocupación')
    fototipo = fields.Selection(
        FOTOTIPO_SELECTION, string='Fototipo (Fitzpatrick)',
        help='Tipo de piel según la escala de Fitzpatrick. Relevante para '
             'tratamientos con láser y luz.',
    )

    # --- Antecedentes relevantes para tratamientos estéticos ---
    antecedentes = fields.Text(
        string='Antecedentes / condiciones',
        help='Enfermedades o condiciones relevantes (diabetes, hipertensión, '
             'tiroides, embarazo/lactancia, etc.).',
    )
    alergias = fields.Text(
        string='Alergias',
        help='Alergias a medicamentos, anestésicos, productos, etc.',
    )
    medicacion_actual = fields.Text(string='Medicación actual')
    cirugias = fields.Text(string='Cirugías / procedimientos previos')
    notas = fields.Text(string='Notas')

    # --- Turnos separados (reservados/confirmados) — solo lectura ---
    turno_ids = fields.One2many(
        'in_estetica.turno', 'paciente_id', string='Turnos agendados',
        domain=[('state', 'in', ('reserved', 'confirmed', 'in_progress'))],
    )
    turno_historico_ids = fields.One2many(
        'in_estetica.turno', 'paciente_id', string='Turnos atendidos',
        domain=[('state', '=', 'done')],
    )
    turno_count = fields.Integer(
        string='Turnos agendados', compute='_compute_turno_count',
    )

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, index=True,
    )

    @api.depends('turno_ids')
    def _compute_turno_count(self):
        for rec in self:
            rec.turno_count = len(rec.turno_ids)

    def action_ver_turnos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Turnos de %s') % self.name,
            'res_model': 'in_estetica.turno',
            'view_mode': 'list,calendar,form',
            'domain': [('paciente_id', '=', self.id)],
            'context': {'default_paciente_id': self.id},
        }

    # ------------------------------------------------------------------

    @api.depends('fecha_nacimiento')
    def _compute_edad(self):
        hoy = date.today()
        for rec in self:
            if not rec.fecha_nacimiento:
                rec.edad = 0
                continue
            fn = rec.fecha_nacimiento
            rec.edad = hoy.year - fn.year - (
                (hoy.month, hoy.day) < (fn.month, fn.day)
            )

    @api.constrains('fecha_nacimiento')
    def _check_fecha_nacimiento(self):
        hoy = date.today()
        for rec in self:
            if rec.fecha_nacimiento and rec.fecha_nacimiento > hoy:
                raise ValidationError(_(
                    'La fecha de nacimiento no puede ser futura.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref_paciente', _('Nuevo')) == _('Nuevo'):
                vals['ref_paciente'] = self.env['ir.sequence'].next_by_code(
                    'in_estetica.paciente'
                ) or _('Nuevo')
            vals.setdefault('is_company', False)
            vals.setdefault('company_type', 'person')
        return super().create(vals_list)

    def unlink(self):
        """Restringe el borrado a Innatum Admin / System y arrastra el
        partner asociado."""
        es_innatum_admin = self.env.user.has_group(
            'in_estetica_control.group_innatum_admin'
        )
        es_system = self.env.user.has_group('base.group_system')
        if not (es_innatum_admin or es_system):
            raise AccessError(_(
                'No tienes permiso para eliminar pacientes. Esa acción está '
                'reservada al Administrador Innatum.'
            ))
        partners = self.mapped('partner_id')
        result = super().unlink()
        if partners:
            partners.sudo().unlink()
        return result
