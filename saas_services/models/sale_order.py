import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # === CITAS ===
    appointment_invite_id = fields.Many2one(
        'appointment.invite',
        string='Invitación de Cita',
        copy=False
    )
    appointment_invite_url = fields.Char(
        string='URL de Cita',
        compute='_compute_appointment_invite_url'
    )
    has_appointment_products = fields.Boolean(
        compute='_compute_has_appointment_products'
    )

    @api.depends('appointment_invite_id')
    def _compute_appointment_invite_url(self):
        for order in self:
            if order.appointment_invite_id:
                order.appointment_invite_url = order.appointment_invite_id.book_url
            else:
                order.appointment_invite_url = False

    @api.depends('order_line.product_id.require_appointment')
    def _compute_has_appointment_products(self):
        for order in self:
            order.has_appointment_products = any(
                line.product_id.require_appointment
                for line in order.order_line
                if line.product_id
            )

    def action_confirm(self):
        """Override para crear citas al confirmar"""
        res = super().action_confirm()

        for order in self:
            # Crear invitaciones de cita
            order._create_appointment_invites()

            # Enviar email con información
            order._send_service_confirmation_email()

        return res

    def _create_appointment_invites(self):
        """Crear invitaciones de cita para productos que lo requieran"""
        self.ensure_one()

        appointment_types = self.order_line.mapped(
            'product_id.appointment_type_id'
        ).filtered(lambda t: t)

        if not appointment_types:
            return

        # Crear una única invitación con todos los tipos de cita
        invite = self.env['appointment.invite'].create({
            'appointment_type_ids': [(6, 0, appointment_types.ids)],
            'short_code': self._generate_appointment_code(),
        })

        self.appointment_invite_id = invite

        _logger.info(
            f"Creada invitación de cita para orden {self.name}: {invite.book_url}"
        )

    def _generate_appointment_code(self):
        """Generar código único para la cita"""
        import hashlib
        hash_suffix = hashlib.md5(
            f"{self.name}{self.id}".encode()
        ).hexdigest()[:6]
        return f"cita-{self.name.lower().replace('/', '-')}-{hash_suffix}"

    def _send_service_confirmation_email(self):
        """Enviar email de confirmación con links de cita"""
        self.ensure_one()

        if not self.has_appointment_products:
            return

        template = self.env.ref(
            'saas_services.email_service_confirmation',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)

    def action_open_appointment_link(self):
        """Abrir link de cita en nueva pestaña"""
        self.ensure_one()
        if self.appointment_invite_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.appointment_invite_url,
                'target': 'new',
            }
