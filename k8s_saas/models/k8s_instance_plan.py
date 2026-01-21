import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class K8sInstancePlan(models.Model):
    _name = 'k8s.instance.plan'
    _description = 'Plan de Instancia Kubernetes'
    _order = 'sequence, id'

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Codigo', required=True, help='Codigo unico del plan (ej: basic, pro, enterprise)')
    description = fields.Text('Descripcion')
    active = fields.Boolean('Activo', default=True)
    sequence = fields.Integer('Secuencia', default=10)

    # Cluster especifico (opcional)
    cluster_id = fields.Many2one(
        'k8s.cluster',
        string='Cluster Especifico',
        ondelete='set null',
        help='Si se especifica, este plan solo esta disponible en este cluster'
    )

    # Templates de manifiestos que usa este plan
    manifest_template_ids = fields.Many2many(
        'k8s.manifest.template',
        'k8s_plan_manifest_rel',
        'plan_id',
        'manifest_id',
        string='Templates de Manifiestos'
    )

    # Recursos
    resources_cpu_limit = fields.Char('CPU Limite', default='2000m', help='Ej: 1000m, 2000m, 4000m')
    resources_cpu_request = fields.Char('CPU Request', default='500m')
    resources_memory_limit = fields.Char('Memoria Limite', default='4Gi', help='Ej: 2Gi, 4Gi, 8Gi')
    resources_memory_request = fields.Char('Memoria Request', default='1Gi')
    storage_size = fields.Char('Almacenamiento', default='20Gi', help='Tamano del PVC')

    # Limites
    max_users = fields.Integer('Max Usuarios', default=0, help='0 = ilimitado')
    max_databases = fields.Integer('Max Bases de Datos', default=1)

    # Imagen Docker
    odoo_image = fields.Char('Imagen Docker', default='odoo:19.0')

    # Producto asociado
    product_ids = fields.Many2many(
        'product.template',
        'k8s_plan_product_rel',
        'plan_id',
        'product_id',
        string='Productos Asociados'
    )

    # Estadisticas
    instance_count = fields.Integer('Instancias', compute='_compute_instance_count')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'El codigo del plan debe ser unico'),
    ]

    @api.depends()
    def _compute_instance_count(self):
        for plan in self:
            plan.instance_count = self.env['k8s.instance'].search_count([
                ('plan_id', '=', plan.id)
            ])

    def get_resource_variables(self):
        """
        Retorna un diccionario con las variables de recursos para renderizar templates.
        """
        self.ensure_one()
        return {
            'cpu_limit': self.resources_cpu_limit or '2000m',
            'cpu_request': self.resources_cpu_request or '500m',
            'memory_limit': self.resources_memory_limit or '4Gi',
            'memory_request': self.resources_memory_request or '1Gi',
            'storage_size': self.storage_size or '20Gi',
            'odoo_image': self.odoo_image or 'odoo:19.0',
        }

    def get_manifest_templates(self, cluster_id=None):
        """
        Obtiene los templates de manifiestos ordenados por secuencia.
        Incluye templates globales y especificos del cluster.

        :param cluster_id: ID del cluster (para filtrar templates especificos)
        :return: recordset de k8s.manifest.template ordenados
        """
        self.ensure_one()

        templates = self.manifest_template_ids.filtered(lambda t: t.active)

        if cluster_id:
            # Filtrar: templates globales O templates del cluster especifico
            templates = templates.filtered(
                lambda t: not t.cluster_id or t.cluster_id.id == cluster_id
            )

        return templates.sorted(key=lambda t: t.sequence)

    def action_view_instances(self):
        """Ver instancias con este plan"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Instancias - %s') % self.name,
            'res_model': 'k8s.instance',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
