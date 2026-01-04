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

    # === SKILLS REQUERIDOS ===
    required_skill_ids = fields.Many2many(
        'saas.skill',
        string='Skills Requeridos',
        help='Colaboradores con estos skills pueden trabajar este servicio'
    )

    # === CONFIGURACIÓN DE INSTANCIA K8S ===
    creates_k8s_instance = fields.Boolean(
        string='Crea Instancia K8s',
        help='Al confirmar, se crea una instancia de Odoo en Kubernetes'
    )
    k8s_template_id = fields.Many2one(
        'k8s.instance.template',
        string='Template de Instancia',
        help='Configuración base para la instancia'
    )

    # === CONFIGURACIÓN DE N8N ===
    is_n8n_service = fields.Boolean(
        string='Es Servicio N8N',
        help='Este producto está relacionado con automatizaciones N8N'
    )
    n8n_workflow_template_id = fields.Char(
        string='Template N8N ID',
        help='ID del workflow template en N8N'
    )
