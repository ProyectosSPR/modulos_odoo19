import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
        'subscription_id',
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

        # Get default cluster
        cluster = Cluster.search([('state', '=', 'connected')], limit=1)
        if not cluster:
            _logger.warning("No connected K8s cluster found")
            return

        for line in self.order_line:
            product = line.product_id

            # Check if product creates K8s instance
            if hasattr(product, 'creates_k8s_instance') and product.creates_k8s_instance:
                # Check if instance already exists for this line
                if line.k8s_instance_id:
                    continue

                # Create instance
                instance_name = f"{self.partner_id.name} - {product.name}"

                instance = Instance.create({
                    'name': instance_name,
                    'cluster_id': cluster.id,
                    'partner_id': self.partner_id.id,
                    'subscription_id': self.id if self.is_subscription else False,
                    'odoo_version': '19.0',
                })

                line.k8s_instance_id = instance.id

                _logger.info(f"Created K8s instance {instance.name} for order {self.name}")

                # Auto-create the instance in K8s
                try:
                    instance.action_create_instance()
                except Exception as e:
                    _logger.error(f"Error auto-creating K8s instance: {e}")

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
            'view_mode': 'list,form',
            'domain': [('subscription_id', '=', self.id)],
            'context': {
                'default_subscription_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
