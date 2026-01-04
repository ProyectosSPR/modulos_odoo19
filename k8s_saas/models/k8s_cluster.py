import logging
import base64
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False
    _logger.warning("kubernetes library not installed. K8s features will be limited.")


class K8sCluster(models.Model):
    _name = 'k8s.cluster'
    _description = 'Kubernetes Cluster'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', required=True, tracking=True)
    active = fields.Boolean('Activo', default=True)

    # Connection
    connection_type = fields.Selection([
        ('kubeconfig', 'Kubeconfig File'),
        ('ssh_tunnel', 'SSH Tunnel'),
        ('direct', 'Direct API'),
    ], string='Tipo de Conexión', default='kubeconfig', required=True)

    kubeconfig = fields.Text('Kubeconfig (YAML)', help='Contenido del archivo kubeconfig')
    api_server = fields.Char('API Server URL')
    api_token = fields.Char('API Token')

    # SSH Tunnel
    ssh_host = fields.Char('SSH Host')
    ssh_port = fields.Integer('SSH Port', default=22)
    ssh_user = fields.Char('SSH User')
    ssh_password = fields.Char('SSH Password')
    ssh_key = fields.Text('SSH Private Key')

    # Default namespace
    default_namespace = fields.Char('Namespace por Defecto', default='default')

    # Cloudflare
    cloudflare_tunnel_id = fields.Char('Cloudflare Tunnel ID')
    cloudflare_zone = fields.Char('Cloudflare Zone (dominio)')

    # Database
    db_host = fields.Char('DB Host', default='postgres')
    db_port = fields.Integer('DB Port', default=5432)
    db_admin_user = fields.Char('DB Admin User', default='postgres')
    db_admin_password = fields.Char('DB Admin Password')

    # Resources
    instance_ids = fields.One2many('k8s.instance', 'cluster_id', string='Instancias')
    instance_count = fields.Integer(compute='_compute_instance_count', string='# Instancias')

    # Status
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('connected', 'Conectado'),
        ('error', 'Error'),
    ], string='Estado', default='draft', tracking=True)
    last_check = fields.Datetime('Última Verificación')
    connection_error = fields.Text('Error de Conexión')

    # Templates
    odoo_image = fields.Char(
        'Imagen Docker Odoo',
        default='odoo:19.0',
        help='Imagen Docker para nuevas instancias'
    )
    default_workers = fields.Integer('Workers por Defecto', default=2)
    default_memory_limit = fields.Char('Límite de Memoria', default='2Gi')
    default_cpu_limit = fields.Char('Límite de CPU', default='1000m')

    @api.depends('instance_ids')
    def _compute_instance_count(self):
        for cluster in self:
            cluster.instance_count = len(cluster.instance_ids)

    def _get_k8s_client(self):
        """Get Kubernetes API client"""
        self.ensure_one()

        if not K8S_AVAILABLE:
            raise UserError(_('La librería kubernetes no está instalada.'))

        try:
            if self.connection_type == 'kubeconfig':
                if not self.kubeconfig:
                    raise UserError(_('No se ha configurado el kubeconfig.'))

                # Load kubeconfig from string
                import tempfile
                import os

                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write(self.kubeconfig)
                    kubeconfig_path = f.name

                try:
                    config.load_kube_config(config_file=kubeconfig_path)
                finally:
                    os.unlink(kubeconfig_path)

            elif self.connection_type == 'direct':
                if not self.api_server or not self.api_token:
                    raise UserError(_('Se requiere API Server y Token.'))

                configuration = client.Configuration()
                configuration.host = self.api_server
                configuration.api_key = {"authorization": f"Bearer {self.api_token}"}
                configuration.verify_ssl = False
                client.Configuration.set_default(configuration)

            else:
                raise UserError(_('Tipo de conexión SSH no implementado aún.'))

            return client.CoreV1Api(), client.AppsV1Api()

        except Exception as e:
            _logger.error(f"Error connecting to K8s cluster: {e}")
            raise UserError(_('Error conectando al cluster: %s') % str(e))

    def action_test_connection(self):
        """Test connection to the Kubernetes cluster"""
        self.ensure_one()

        try:
            core_api, apps_api = self._get_k8s_client()

            # Try to list namespaces
            namespaces = core_api.list_namespace()
            ns_names = [ns.metadata.name for ns in namespaces.items]

            self.write({
                'state': 'connected',
                'last_check': fields.Datetime.now(),
                'connection_error': False,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('Namespaces encontrados: %s') % ', '.join(ns_names[:5]),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            self.write({
                'state': 'error',
                'last_check': fields.Datetime.now(),
                'connection_error': str(e),
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de Conexión'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_instances(self):
        """View instances in this cluster"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Instancias en %s') % self.name,
            'res_model': 'k8s.instance',
            'view_mode': 'list,form',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id},
        }

    def create_database(self, db_name, owner=None):
        """Create a new PostgreSQL database in the cluster"""
        self.ensure_one()

        if not owner:
            owner = db_name

        try:
            import paramiko

            # This would typically connect to the postgres pod or service
            # For now, we'll use psycopg2 if we can reach the DB directly
            import psycopg2

            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_admin_user,
                password=self.db_admin_password,
                dbname='postgres'
            )
            conn.autocommit = True

            with conn.cursor() as cur:
                # Create user if not exists
                cur.execute(f"SELECT 1 FROM pg_roles WHERE rolname = %s", (owner,))
                if not cur.fetchone():
                    cur.execute(f"CREATE USER {owner} WITH PASSWORD %s", (owner,))

                # Create database
                cur.execute(f"CREATE DATABASE {db_name} OWNER {owner}")

            conn.close()
            _logger.info(f"Created database {db_name} in cluster {self.name}")
            return True

        except Exception as e:
            _logger.error(f"Error creating database: {e}")
            raise UserError(_('Error creando base de datos: %s') % str(e))

    def get_deployment_template(self, instance_name, db_name, subdomain):
        """Generate Kubernetes deployment YAML for a new Odoo instance"""
        self.ensure_one()

        deployment = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {
                'name': instance_name,
                'namespace': self.default_namespace,
                'labels': {
                    'app': 'odoo',
                    'instance': instance_name,
                }
            },
            'spec': {
                'replicas': 1,
                'selector': {
                    'matchLabels': {
                        'app': 'odoo',
                        'instance': instance_name,
                    }
                },
                'template': {
                    'metadata': {
                        'labels': {
                            'app': 'odoo',
                            'instance': instance_name,
                        }
                    },
                    'spec': {
                        'containers': [{
                            'name': 'odoo',
                            'image': self.odoo_image,
                            'ports': [{'containerPort': 8069}],
                            'env': [
                                {'name': 'HOST', 'value': self.db_host},
                                {'name': 'PORT', 'value': str(self.db_port)},
                                {'name': 'USER', 'value': db_name},
                                {'name': 'PASSWORD', 'value': db_name},
                                {'name': 'DATABASE', 'value': db_name},
                            ],
                            'resources': {
                                'limits': {
                                    'memory': self.default_memory_limit,
                                    'cpu': self.default_cpu_limit,
                                },
                                'requests': {
                                    'memory': '512Mi',
                                    'cpu': '250m',
                                }
                            }
                        }]
                    }
                }
            }
        }

        service = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {
                'name': f'{instance_name}-svc',
                'namespace': self.default_namespace,
            },
            'spec': {
                'selector': {
                    'app': 'odoo',
                    'instance': instance_name,
                },
                'ports': [{
                    'port': 8069,
                    'targetPort': 8069,
                }]
            }
        }

        return deployment, service
