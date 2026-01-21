import logging
import base64
import json
import tempfile
import os
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

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    _logger.warning("PyYAML library not installed.")


class K8sCluster(models.Model):
    _name = 'k8s.cluster'
    _description = 'Kubernetes Cluster'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char('Nombre', required=True, tracking=True)
    code = fields.Char('Codigo', required=True, help='Codigo unico del cluster (ej: local, do-us, do-eu)')
    description = fields.Text('Descripcion')
    active = fields.Boolean('Activo', default=True)
    sequence = fields.Integer('Secuencia', default=10)
    is_default = fields.Boolean('Es Predeterminado', default=False, help='Cluster por defecto para nuevas instancias')

    # ==================== CONEXION K8S ====================
    connection_type = fields.Selection([
        ('kubeconfig', 'Kubeconfig File'),
        ('direct', 'Direct API (Token)'),
    ], string='Tipo de Conexion', default='kubeconfig', required=True)

    kubeconfig = fields.Text('Kubeconfig (YAML)', help='Contenido completo del archivo kubeconfig')
    api_server = fields.Char('API Server URL', help='URL del API server (para conexion directa)')
    api_token = fields.Char('API Token', help='Token de servicio para conexion directa')

    # Namespace por defecto
    default_namespace = fields.Char('Namespace por Defecto', default='default')

    # ==================== CLOUDFLARE ====================
    cloudflare_enabled = fields.Boolean('Cloudflare Habilitado', default=True)
    cloudflare_tunnel_token = fields.Char('Cloudflare Tunnel Token', help='Token del tunnel (usado por cloudflared)')
    cloudflare_configmap_name = fields.Char('ConfigMap de Cloudflare', default='cloudflared-config')
    cloudflare_configmap_namespace = fields.Char('Namespace del ConfigMap', default='default')
    cloudflare_deployment_name = fields.Char('Deployment Cloudflared', default='cloudflared')
    cloudflare_domain = fields.Char('Dominio Base', help='Ej: tudominio.com - Las instancias seran subdominio.tudominio.com')

    # ==================== POSTGRESQL ====================
    db_host = fields.Char('DB Host', default='postgres', help='Hostname o servicio de PostgreSQL')
    db_port = fields.Integer('DB Port', default=5432)
    db_admin_user = fields.Char('DB Admin User', default='postgres')
    db_admin_password = fields.Char('DB Admin Password')

    # ==================== RECURSOS POR DEFECTO ====================
    odoo_image = fields.Char('Imagen Docker Odoo', default='odoo:19.0')
    default_cpu_limit = fields.Char('CPU Limite Default', default='2000m')
    default_memory_limit = fields.Char('Memoria Limite Default', default='4Gi')
    default_storage_size = fields.Char('Storage Default', default='20Gi')

    # ==================== RELACIONES ====================
    manifest_template_ids = fields.One2many('k8s.manifest.template', 'cluster_id', string='Templates Especificos')
    plan_ids = fields.One2many('k8s.instance.plan', 'cluster_id', string='Planes Especificos')
    instance_ids = fields.One2many('k8s.instance', 'cluster_id', string='Instancias')

    # Contadores
    instance_count = fields.Integer('Instancias', compute='_compute_counts')
    running_count = fields.Integer('Ejecutando', compute='_compute_counts')

    # ==================== ESTADO ====================
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('connected', 'Conectado'),
        ('error', 'Error'),
    ], string='Estado', default='draft', tracking=True)
    last_check = fields.Datetime('Ultima Verificacion')
    connection_error = fields.Text('Error de Conexion')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'El codigo del cluster debe ser unico'),
    ]

    @api.depends('instance_ids', 'instance_ids.state')
    def _compute_counts(self):
        for cluster in self:
            cluster.instance_count = len(cluster.instance_ids)
            cluster.running_count = len(cluster.instance_ids.filtered(lambda i: i.state == 'running'))

    @api.constrains('is_default')
    def _check_single_default(self):
        """Solo puede haber un cluster por defecto"""
        for cluster in self:
            if cluster.is_default:
                others = self.search([('is_default', '=', True), ('id', '!=', cluster.id)])
                if others:
                    others.write({'is_default': False})

    # ==================== CONEXION K8S ====================

    def _get_k8s_client(self):
        """Obtiene cliente de API de Kubernetes"""
        self.ensure_one()

        if not K8S_AVAILABLE:
            raise UserError(_('La libreria kubernetes no esta instalada. Ejecute: pip install kubernetes'))

        try:
            if self.connection_type == 'kubeconfig':
                if not self.kubeconfig:
                    raise UserError(_('No se ha configurado el kubeconfig.'))

                # Guardar kubeconfig en archivo temporal
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write(self.kubeconfig)
                    kubeconfig_path = f.name

                try:
                    config.load_kube_config(config_file=kubeconfig_path)
                finally:
                    os.unlink(kubeconfig_path)

            elif self.connection_type == 'direct':
                if not self.api_server or not self.api_token:
                    raise UserError(_('Se requiere API Server y Token para conexion directa.'))

                configuration = client.Configuration()
                configuration.host = self.api_server
                configuration.api_key = {"authorization": f"Bearer {self.api_token}"}
                configuration.verify_ssl = False
                client.Configuration.set_default(configuration)

            else:
                raise UserError(_('Tipo de conexion no soportado.'))

            return client.CoreV1Api(), client.AppsV1Api()

        except Exception as e:
            _logger.error(f"Error connecting to K8s cluster {self.name}: {e}")
            raise UserError(_('Error conectando al cluster: %s') % str(e))

    def action_test_connection(self):
        """Probar conexion al cluster"""
        self.ensure_one()

        try:
            core_api, apps_api = self._get_k8s_client()

            # Intentar listar namespaces
            namespaces = core_api.list_namespace()
            ns_names = [ns.metadata.name for ns in namespaces.items]

            self.write({
                'state': 'connected',
                'last_check': fields.Datetime.now(),
                'connection_error': False,
            })

            self.message_post(body=_('Conexion exitosa. Namespaces: %s') % ', '.join(ns_names[:5]))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexion Exitosa'),
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
                    'title': _('Error de Conexion'),
                    'message': str(e)[:200],
                    'type': 'danger',
                    'sticky': True,
                }
            }

    # ==================== POSTGRESQL ====================

    def create_database(self, db_name, db_user, db_password):
        """Crear base de datos y usuario en PostgreSQL"""
        self.ensure_one()

        if not self.db_host or not self.db_admin_password:
            raise UserError(_('Configuracion de PostgreSQL incompleta.'))

        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port or 5432,
                user=self.db_admin_user or 'postgres',
                password=self.db_admin_password,
                dbname='postgres'
            )
            conn.autocommit = True

            with conn.cursor() as cur:
                # Crear usuario si no existe
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (db_user,))
                if not cur.fetchone():
                    # Escapar password correctamente
                    cur.execute(
                        f"CREATE USER \"{db_user}\" WITH PASSWORD %s",
                        (db_password,)
                    )
                    _logger.info(f"Created PostgreSQL user: {db_user}")

                # Crear base de datos si no existe
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                if not cur.fetchone():
                    cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{db_user}"')
                    _logger.info(f"Created PostgreSQL database: {db_name}")

            conn.close()
            return True

        except ImportError:
            raise UserError(_('psycopg2 no esta instalado. Ejecute: pip install psycopg2-binary'))
        except Exception as e:
            _logger.error(f"Error creating database: {e}")
            raise UserError(_('Error creando base de datos: %s') % str(e))

    def drop_database(self, db_name, db_user):
        """Eliminar base de datos y usuario de PostgreSQL"""
        self.ensure_one()

        try:
            import psycopg2

            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port or 5432,
                user=self.db_admin_user or 'postgres',
                password=self.db_admin_password,
                dbname='postgres'
            )
            conn.autocommit = True

            with conn.cursor() as cur:
                # Terminar conexiones activas
                cur.execute("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = %s
                    AND pid <> pg_backend_pid()
                """, (db_name,))

                # Eliminar base de datos
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                if cur.fetchone():
                    cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                    _logger.info(f"Dropped database: {db_name}")

                # Eliminar usuario
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (db_user,))
                if cur.fetchone():
                    cur.execute(f'DROP USER IF EXISTS "{db_user}"')
                    _logger.info(f"Dropped user: {db_user}")

            conn.close()
            return True

        except Exception as e:
            _logger.error(f"Error dropping database: {e}")
            raise UserError(_('Error eliminando base de datos: %s') % str(e))

    # ==================== CLOUDFLARE ====================

    def update_cloudflare_config(self, subdomain, service_name, service_namespace, action='add'):
        """
        Actualizar ConfigMap de Cloudflare para agregar/eliminar una ruta.

        :param subdomain: Subdominio de la instancia
        :param service_name: Nombre del servicio K8s
        :param service_namespace: Namespace del servicio
        :param action: 'add' o 'remove'
        """
        self.ensure_one()

        if not self.cloudflare_enabled:
            _logger.info("Cloudflare no habilitado para este cluster")
            return True

        if not YAML_AVAILABLE:
            raise UserError(_('PyYAML no esta instalado.'))

        try:
            core_api, _ = self._get_k8s_client()

            # Leer ConfigMap actual
            try:
                configmap = core_api.read_namespaced_config_map(
                    name=self.cloudflare_configmap_name,
                    namespace=self.cloudflare_configmap_namespace or 'default'
                )
            except ApiException as e:
                if e.status == 404:
                    raise UserError(_('ConfigMap de Cloudflare no encontrado: %s') % self.cloudflare_configmap_name)
                raise

            # Obtener config.yaml del ConfigMap
            config_yaml = configmap.data.get('config.yaml', '')
            if not config_yaml:
                raise UserError(_('ConfigMap no contiene config.yaml'))

            cf_config = yaml.safe_load(config_yaml)

            # Preparar nueva entrada
            hostname = f"{subdomain}.{self.cloudflare_domain}"
            service_url = f"http://{service_name}.{service_namespace}:8069"

            if action == 'add':
                # Buscar lista de ingress
                ingress_list = cf_config.get('ingress', [])

                # Verificar si ya existe
                exists = any(
                    entry.get('hostname') == hostname
                    for entry in ingress_list
                    if isinstance(entry, dict)
                )

                if not exists:
                    # Insertar antes del catch-all (ultimo elemento)
                    new_entry = {
                        'hostname': hostname,
                        'service': service_url
                    }

                    # El ultimo debe ser el catch-all (sin hostname)
                    if ingress_list and 'hostname' not in ingress_list[-1]:
                        ingress_list.insert(-1, new_entry)
                    else:
                        ingress_list.append(new_entry)

                    cf_config['ingress'] = ingress_list
                    _logger.info(f"Added Cloudflare route: {hostname} -> {service_url}")

            elif action == 'remove':
                ingress_list = cf_config.get('ingress', [])
                cf_config['ingress'] = [
                    entry for entry in ingress_list
                    if not (isinstance(entry, dict) and entry.get('hostname') == hostname)
                ]
                _logger.info(f"Removed Cloudflare route: {hostname}")

            # Actualizar ConfigMap
            configmap.data['config.yaml'] = yaml.dump(cf_config, default_flow_style=False)
            core_api.replace_namespaced_config_map(
                name=self.cloudflare_configmap_name,
                namespace=self.cloudflare_configmap_namespace or 'default',
                body=configmap
            )

            # Reiniciar deployment de cloudflared para aplicar cambios
            self._restart_cloudflared()

            return True

        except Exception as e:
            _logger.error(f"Error updating Cloudflare config: {e}")
            raise UserError(_('Error actualizando Cloudflare: %s') % str(e))

    def _restart_cloudflared(self):
        """Reiniciar deployment de cloudflared para aplicar cambios"""
        self.ensure_one()

        if not self.cloudflare_deployment_name:
            return

        try:
            _, apps_api = self._get_k8s_client()

            # Patch para forzar restart (cambiar annotation)
            patch = {
                'spec': {
                    'template': {
                        'metadata': {
                            'annotations': {
                                'kubectl.kubernetes.io/restartedAt': fields.Datetime.now().isoformat()
                            }
                        }
                    }
                }
            }

            apps_api.patch_namespaced_deployment(
                name=self.cloudflare_deployment_name,
                namespace=self.cloudflare_configmap_namespace or 'default',
                body=patch
            )

            _logger.info(f"Restarted cloudflared deployment: {self.cloudflare_deployment_name}")

        except Exception as e:
            _logger.warning(f"Could not restart cloudflared: {e}")

    # ==================== ACCIONES ====================

    def action_view_instances(self):
        """Ver instancias de este cluster"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Instancias en %s') % self.name,
            'res_model': 'k8s.instance',
            'view_mode': 'list,form',
            'domain': [('cluster_id', '=', self.id)],
            'context': {'default_cluster_id': self.id},
        }

    def action_view_templates(self):
        """Ver templates especificos de este cluster"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Templates de %s') % self.name,
            'res_model': 'k8s.manifest.template',
            'view_mode': 'list,form',
            'domain': ['|', ('cluster_id', '=', self.id), ('cluster_id', '=', False)],
            'context': {'default_cluster_id': self.id},
        }
