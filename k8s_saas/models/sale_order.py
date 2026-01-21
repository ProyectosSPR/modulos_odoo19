import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    creates_k8s_instance = fields.Boolean(
        'Crea Instancia K8s',
        help='Al vender este producto se creara una instancia de Odoo en Kubernetes'
    )
    k8s_plan_id = fields.Many2one(
        'k8s.instance.plan',
        string='Plan K8s',
        help='Plan de recursos para la instancia'
    )
    k8s_managed_by_us = fields.Boolean(
        'Administrado por Nosotros',
        default=True,
        help='Si es True, nosotros administramos la instancia. Si es False, el cliente la administra.'
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    k8s_instance_id = fields.Many2one(
        'k8s.instance',
        string='Instancia K8s',
        copy=False
    )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    k8s_instance_ids = fields.One2many(
        'k8s.instance',
        'sale_order_id',
        string='Instancias K8s'
    )
    k8s_instance_count = fields.Integer(
        compute='_compute_k8s_instance_count',
        string='# Instancias'
    )

    @api.depends('k8s_instance_ids')
    def _compute_k8s_instance_count(self):
        for order in self:
            order.k8s_instance_count = len(order.k8s_instance_ids)

    def _create_k8s_instances(self):
        """Create K8s instances for products that require them"""
        self.ensure_one()

        Instance = self.env['k8s.instance']
        Cluster = self.env['k8s.cluster']

        for line in self.order_line:
            product = line.product_id.product_tmpl_id

            # Check if product creates K8s instance
            if not product.creates_k8s_instance:
                continue

            # Check if instance already exists for this line
            if line.k8s_instance_id:
                continue

            # Get plan from product or default
            plan = product.k8s_plan_id
            if not plan:
                plan = self.env['k8s.instance.plan'].search([], limit=1)
                if not plan:
                    _logger.warning(f"No K8s plan found for product {product.name}")
                    continue

            # Get cluster - prefer plan's cluster, then default, then any connected
            cluster = plan.cluster_id
            if not cluster:
                cluster = Cluster.search([('is_default', '=', True), ('state', '=', 'connected')], limit=1)
            if not cluster:
                cluster = Cluster.search([('state', '=', 'connected')], limit=1)
            if not cluster:
                _logger.warning("No connected K8s cluster found")
                continue

            # Create instance name
            instance_name = f"{self.partner_id.name} - {product.name}"
            if line.product_uom_qty > 1:
                # If multiple quantities, add sequence
                existing_count = Instance.search_count([
                    ('partner_id', '=', self.partner_id.id),
                    ('plan_id', '=', plan.id)
                ])
                instance_name = f"{self.partner_id.name} - {product.name} #{existing_count + 1}"

            # Determine if managed by us
            managed_by_us = product.k8s_managed_by_us

            # Create instance
            instance = Instance.create({
                'name': instance_name,
                'cluster_id': cluster.id,
                'plan_id': plan.id,
                'partner_id': self.partner_id.id,
                'sale_order_id': self.id,
                'subscription_id': self.id if self.is_subscription else False,
                'managed_by_us': managed_by_us,
            })

            line.k8s_instance_id = instance.id

            _logger.info(f"Created K8s instance {instance.name} for order {self.name}")

            # Auto-create the instance in K8s only if managed by us
            if managed_by_us:
                try:
                    instance.action_create_instance()
                except Exception as e:
                    _logger.error(f"Error auto-creating K8s instance: {e}")
                    # Don't fail the order, just log the error
                    instance.message_post(body=_('Error al crear instancia automaticamente: %s') % str(e))

    def action_confirm(self):
        """Override to create K8s instances on confirmation"""
        res = super().action_confirm()

        for order in self:
            order._create_k8s_instances()

        return res

    def action_view_k8s_instances(self):
        """View K8s instances linked to this order"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Instancias K8s'),
            'res_model': 'k8s.instance',
            'view_mode': 'kanban,list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
