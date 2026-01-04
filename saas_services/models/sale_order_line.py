from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # === CAMPOS RELACIONADOS ===
    service_category = fields.Selection(
        related='product_id.service_category',
        string='Categoría de Servicio',
        store=True
    )
    require_appointment = fields.Boolean(
        related='product_id.require_appointment',
        store=True
    )
    creates_k8s_instance = fields.Boolean(
        related='product_id.creates_k8s_instance',
        store=True
    )

    # === ASIGNACIÓN ===
    assigned_collaborator_id = fields.Many2one(
        'saas.collaborator',
        string='Colaborador Asignado',
        help='Colaborador que trabajará esta línea específica'
    )
