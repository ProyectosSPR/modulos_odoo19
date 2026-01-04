from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # === INTEGRACIÓN CON CITAS ===
    appointment_type_id = fields.Many2one(
        'appointment.type',
        string='Tipo de Cita',
        help='Al confirmar la venta, el cliente podrá agendar esta cita'
    )
    require_appointment = fields.Boolean(
        string='Requiere Agendar Cita',
        help='El cliente debe agendar una cita inicial después de comprar'
    )

    # === TIPO DE SERVICIO ===
    service_category = fields.Selection([
        ('consulting', 'Consultoría'),
        ('configuration', 'Configuración'),
        ('development', 'Desarrollo'),
        ('training', 'Capacitación'),
        ('support', 'Soporte Técnico'),
        ('hosting', 'Hosting/Instancia'),
        ('automation', 'Automatización N8N'),
        ('other', 'Otro'),
    ], string='Categoría de Servicio')

    # === COTIZACIÓN ===
    requires_quotation = fields.Boolean(
        string='Requiere Cotización',
        help='El cliente debe solicitar cotización en lugar de comprar directamente'
    )

    # === CONFIGURACIÓN DE INSTANCIA K8S ===
    # Nota: El campo creates_k8s_instance es procesado por k8s_saas si está instalado
    creates_k8s_instance = fields.Boolean(
        string='Crea Instancia K8s',
        help='Al confirmar, se crea una instancia de Odoo en Kubernetes'
    )
