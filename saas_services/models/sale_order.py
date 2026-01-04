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

    # === INSTANCIAS K8S ===
    saas_instance_ids = fields.One2many(
        'saas.instance',
        'subscription_id',
        string='Instancias SaaS'
    )
    saas_instance_count = fields.Integer(
        compute='_compute_saas_instance_count'
    )

    # === ESTADO DE ASIGNACIÓN ===
    assignment_state = fields.Selection([
        ('pending', 'Pendiente de Asignar'),
        ('assigned', 'Asignado'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
    ], string='Estado de Asignación', default='pending')

    assigned_collaborator_id = fields.Many2one(
        'saas.collaborator',
        string='Colaborador Asignado'
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

    @api.depends('saas_instance_ids')
    def _compute_saas_instance_count(self):
        for order in self:
            order.saas_instance_count = len(order.saas_instance_ids)

    def action_confirm(self):
        """Override para crear citas e instancias al confirmar"""
        res = super().action_confirm()

        for order in self:
            # Crear invitaciones de cita
            order._create_appointment_invites()

            # Crear instancias K8s si aplica
            order._create_k8s_instances()

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
        # Formato: cita-so001-abc123
        import hashlib
        hash_suffix = hashlib.md5(
            f"{self.name}{self.id}".encode()
        ).hexdigest()[:6]
        return f"cita-{self.name.lower().replace('/', '-')}-{hash_suffix}"

    def _create_k8s_instances(self):
        """Crear instancias de Kubernetes para productos que lo requieran"""
        self.ensure_one()

        k8s_products = self.order_line.filtered(
            lambda l: l.product_id.creates_k8s_instance
        )

        if not k8s_products:
            return

        Instance = self.env['saas.instance']

        for line in k8s_products:
            # Verificar si ya existe una instancia para este cliente
            existing = Instance.search([
                ('partner_id', '=', self.partner_id.id),
                ('state', 'not in', ['terminated']),
            ], limit=1)

            if existing:
                _logger.info(
                    f"Cliente {self.partner_id.name} ya tiene instancia: {existing.name}"
                )
                continue

            # Crear nueva instancia
            instance = Instance.create({
                'name': f"{self.partner_id.name} - Odoo",
                'partner_id': self.partner_id.id,
                'subscription_id': self.id,
                'product_id': line.product_id.id,
            })

            _logger.info(
                f"Creada instancia K8s para orden {self.name}: {instance.name}"
            )

    def _send_service_confirmation_email(self):
        """Enviar email de confirmación con links de cita y proyecto"""
        self.ensure_one()

        if not self.has_appointment_products and not self.saas_instance_ids:
            return

        template = self.env.ref(
            'saas_services.email_service_confirmation',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)

    def action_view_saas_instances(self):
        """Abrir vista de instancias SaaS"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Instancias SaaS'),
            'res_model': 'saas.instance',
            'view_mode': 'list,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {'default_subscription_id': self.id},
        }

    def action_open_appointment_link(self):
        """Abrir link de cita en nueva pestaña"""
        self.ensure_one()
        if self.appointment_invite_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.appointment_invite_url,
                'target': 'new',
            }
