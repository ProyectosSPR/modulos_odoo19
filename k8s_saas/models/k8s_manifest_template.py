import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class K8sManifestTemplate(models.Model):
    _name = 'k8s.manifest.template'
    _description = 'Template de Manifiesto Kubernetes'
    _order = 'sequence, id'

    name = fields.Char('Nombre', required=True)
    description = fields.Text('Descripcion')
    active = fields.Boolean('Activo', default=True)
    sequence = fields.Integer('Secuencia', default=10, help='Orden de aplicacion del manifiesto')

    # Tipo de manifiesto
    manifest_type = fields.Selection([
        ('namespace', 'Namespace'),
        ('pvc', 'PersistentVolumeClaim'),
        ('configmap', 'ConfigMap'),
        ('secret', 'Secret'),
        ('deployment', 'Deployment'),
        ('service', 'Service'),
        ('ingress', 'Ingress'),
        ('other', 'Otro'),
    ], string='Tipo', required=True, default='deployment')

    # Contenido YAML
    yaml_content = fields.Text(
        'Contenido YAML',
        required=True,
        help='Manifiesto YAML con variables {{ variable_name }}'
    )

    # Cluster asociado (opcional - si es global aplica a todos)
    cluster_id = fields.Many2one(
        'k8s.cluster',
        string='Cluster',
        ondelete='cascade',
        help='Dejar vacio para que sea global (aplica a todos los clusters)'
    )
    is_global = fields.Boolean(
        'Es Global',
        compute='_compute_is_global',
        store=True
    )

    # Planes que usan este template
    plan_ids = fields.Many2many(
        'k8s.instance.plan',
        'k8s_plan_manifest_rel',
        'manifest_id',
        'plan_id',
        string='Planes'
    )

    # Variables detectadas
    detected_variables = fields.Char(
        'Variables Detectadas',
        compute='_compute_detected_variables',
        store=True
    )

    @api.depends('cluster_id')
    def _compute_is_global(self):
        for record in self:
            record.is_global = not record.cluster_id

    @api.depends('yaml_content')
    def _compute_detected_variables(self):
        for record in self:
            if record.yaml_content:
                # Buscar {{ variable }} en el contenido
                variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', record.yaml_content)
                record.detected_variables = ', '.join(sorted(set(variables)))
            else:
                record.detected_variables = ''

    def render_yaml(self, variables):
        """
        Renderiza el YAML reemplazando las variables.

        :param variables: dict con las variables a reemplazar
        :return: str con el YAML renderizado
        """
        self.ensure_one()

        if not self.yaml_content:
            raise UserError(_('El template no tiene contenido YAML.'))

        yaml_rendered = self.yaml_content

        # Reemplazar variables {{ variable }}
        for key, value in variables.items():
            pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            yaml_rendered = re.sub(pattern, str(value), yaml_rendered)

        # Verificar si quedaron variables sin reemplazar
        remaining = re.findall(r'\{\{\s*(\w+)\s*\}\}', yaml_rendered)
        if remaining:
            _logger.warning(f"Variables sin reemplazar en template {self.name}: {remaining}")

        return yaml_rendered

    @api.constrains('yaml_content')
    def _check_yaml_content(self):
        """Validar que el YAML sea valido (sintaxis basica)"""
        for record in self:
            if record.yaml_content:
                try:
                    import yaml
                    # Reemplazar variables temporalmente para validar
                    test_yaml = re.sub(r'\{\{\s*\w+\s*\}\}', 'test_value', record.yaml_content)
                    yaml.safe_load_all(test_yaml)
                except yaml.YAMLError as e:
                    raise ValidationError(_('Error de sintaxis YAML: %s') % str(e))
                except ImportError:
                    _logger.warning('PyYAML no instalado, no se puede validar sintaxis')

    def action_preview_variables(self):
        """Mostrar las variables disponibles"""
        self.ensure_one()

        available_vars = """
Variables disponibles para usar en los templates:

INSTANCIA:
  {{ instance_name }}     - Nombre tecnico de la instancia
  {{ namespace }}         - Namespace de Kubernetes
  {{ subdomain }}         - Subdominio para la URL

BASE DE DATOS:
  {{ db_host }}           - Host de PostgreSQL
  {{ db_port }}           - Puerto de PostgreSQL
  {{ db_name }}           - Nombre de la base de datos
  {{ db_user }}           - Usuario de la base de datos
  {{ db_password }}       - Password de la base de datos

ODOO:
  {{ admin_password }}    - Password del usuario admin de Odoo
  {{ odoo_image }}        - Imagen Docker de Odoo

RECURSOS:
  {{ cpu_limit }}         - Limite de CPU (ej: 2000m)
  {{ cpu_request }}       - Request de CPU (ej: 500m)
  {{ memory_limit }}      - Limite de memoria (ej: 4Gi)
  {{ memory_request }}    - Request de memoria (ej: 1Gi)
  {{ storage_size }}      - Tamano del PVC (ej: 50Gi)

CLOUDFLARE:
  {{ cloudflare_domain }} - Dominio base de Cloudflare
"""

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Variables Disponibles'),
                'message': available_vars,
                'type': 'info',
                'sticky': True,
            }
        }
