from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaasCollaboratorPayment(models.Model):
    _name = 'saas.collaborator.payment'
    _description = 'Pago a Colaborador'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        'Referencia',
        required=True,
        default=lambda self: _('Nuevo'),
        copy=False
    )
    collaborator_id = fields.Many2one(
        'saas.collaborator',
        string='Colaborador',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    partner_id = fields.Many2one(
        related='collaborator_id.partner_id',
        store=True
    )

    date = fields.Date(
        'Fecha',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    amount = fields.Monetary(
        'Monto',
        required=True,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True, required=True)

    payment_method = fields.Selection([
        ('transfer', 'Transferencia Bancaria'),
        ('paypal', 'PayPal'),
        ('wise', 'Wise'),
        ('crypto', 'Criptomoneda'),
        ('cash', 'Efectivo'),
        ('other', 'Otro'),
    ], string='Método de Pago', default='transfer')

    # Periodo que cubre el pago
    period_start = fields.Date('Periodo Desde')
    period_end = fields.Date('Periodo Hasta')

    # Desglose
    hours_paid = fields.Float('Horas Pagadas')
    rate_applied = fields.Float('Tarifa Aplicada')

    # Referencias
    payment_reference = fields.Char('Referencia de Pago')
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura de Proveedor',
        domain=[('move_type', '=', 'in_invoice')]
    )

    notes = fields.Text('Notas')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Comprobantes'
    )

    # Computo para mostrar balance antes/después
    balance_before = fields.Monetary(
        'Saldo Antes',
        compute='_compute_balance_info',
        currency_field='currency_id'
    )
    balance_after = fields.Monetary(
        'Saldo Después',
        compute='_compute_balance_info',
        currency_field='currency_id'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'saas.collaborator.payment'
                ) or _('Nuevo')
        return super().create(vals_list)

    def _compute_balance_info(self):
        for payment in self:
            if payment.collaborator_id:
                # Balance actual del colaborador
                current_balance = payment.collaborator_id.balance
                if payment.state == 'paid':
                    # Si ya está pagado, el balance actual ya lo refleja
                    payment.balance_after = current_balance
                    payment.balance_before = current_balance + payment.amount
                else:
                    # Si no está pagado, mostrar cómo quedaría
                    payment.balance_before = current_balance
                    payment.balance_after = current_balance - payment.amount
            else:
                payment.balance_before = 0
                payment.balance_after = 0

    def action_confirm(self):
        """Confirmar pago (pendiente de procesar)"""
        for payment in self:
            if payment.state != 'draft':
                raise UserError(_('Solo se pueden confirmar pagos en borrador.'))
            payment.state = 'pending'

    def action_pay(self):
        """Marcar como pagado"""
        for payment in self:
            if payment.state not in ('draft', 'pending'):
                raise UserError(_('Solo se pueden pagar pagos en borrador o pendientes.'))
            payment.state = 'paid'

    def action_cancel(self):
        """Cancelar pago"""
        for payment in self:
            if payment.state == 'paid':
                raise UserError(_('No se pueden cancelar pagos ya realizados.'))
            payment.state = 'cancelled'

    def action_draft(self):
        """Regresar a borrador"""
        for payment in self:
            if payment.state == 'paid':
                raise UserError(_('No se pueden regresar a borrador pagos ya realizados.'))
            payment.state = 'draft'

    @api.onchange('collaborator_id')
    def _onchange_collaborator_id(self):
        if self.collaborator_id:
            self.amount = self.collaborator_id.balance
            self.currency_id = self.collaborator_id.currency_id
            self.rate_applied = self.collaborator_id.rate_amount

    @api.onchange('hours_paid', 'rate_applied')
    def _onchange_hours_rate(self):
        if self.hours_paid and self.rate_applied:
            self.amount = self.hours_paid * self.rate_applied
