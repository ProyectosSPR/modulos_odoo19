import logging
import re
import secrets
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    from kubernetes import client
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class K8sInstance(models.Model):
    _name = 'k8s.instance'
    _description = 'Instancia Odoo en Kubernetes'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Nombre', required=True, tracking=True)
    technical_name = fields.Char(
        'Nombre Tecnico',
        compute='_compute_technical_name',
        store=True,
        help='Nombre valido para Kubernetes (sin espacios ni caracteres especiales)'
    )

    # ==================== RELACIONES PRINCIPALES ====================
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Orden de Venta',
        ondelete='set null',
        tracking=True
    )
    subscription_id = fields.Many2one(
        'sale.order',
        string='Suscripcion',
        domain=[('is_subscription', '=', True)],
        ondelete='set null'
    )

    # ==================== CLUSTER Y PLAN ====================
    cluster_id = fields.Many2one(
        'k8s.cluster',
        string='Cluster',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain=[('state', '=', 'connected')]
    )
    plan_id = fields.Many2one(
        'k8s.instance.plan',
        string='Plan',
        required=True,
        ondelete='restrict',
        tracking=True
    )

    # ==================== CONFIGURACION K8S ====================
    namespace = fields.Char(
        'Namespace',
        compute='_compute_namespace',
        store=True
    )
    subdomain = fields.Char('Subdominio', tracking=True)
    url = fields.Char('URL', compute='_compute_url', store=True)

    # Recursos (heredados del plan pero editables)
    odoo_image = fields.Char('Imagen Docker')
    cpu_limit = fields.Char('CPU Limite')
    memory_limit = fields.Char('Memoria Limite')
    storage_size = fields.Char('Almacenamiento')

    # ==================== BASE DE DATOS ====================
    db_name = fields.Char('Base de Datos', tracking=True)
    db_user = fields.Char('Usuario DB')
    db_password = fields.Char('Password DB')
    admin_password = fields.Char('Password Admin Odoo')

    # ==================== ESTADO ====================
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('creating', 'Creando'),
        ('running', 'Ejecutando'),
        ('stopped', 'Detenido'),
        ('error', 'Error'),
        ('deleted', 'Eliminado'),
    ], string='Estado', default='draft', tracking=True, required=True)

    managed_by_us = fields.Boolean(
        'Administrado por Nosotros',
        default=True,
        help='Si es False, el cliente administra su propia instancia'
    )

    # ==================== K8S RESOURCES ====================
    deployment_name = fields.Char('Deployment Name')
    service_name = fields.Char('Service Name')
    pvc_name = fields.Char('PVC Name')
    pod_status = fields.Char('Estado del Pod')

    # ==================== HISTORICO ====================
    applied_manifest_ids = fields.One2many(
        'k8s.instance.manifest',
        'instance_id',
        string='Manifiestos Aplicados'
    )

    # ==================== FECHAS Y ERRORES ====================
    created_date = fields.Datetime('Fecha de Creacion')
    last_accessed = fields.Datetime('Ultimo Acceso')
    error_message = fields.Text('Mensaje de Error')

    # ==================== COMPUTED ====================

    @api.depends('name')
    def _compute_technical_name(self):
        for instance in self:
            if instance.name:
                # Convertir a minusculas, quitar caracteres especiales
                tech_name = re.sub(r'[^a-z0-9-]', '', instance.name.lower().replace(' ', '-'))
                tech_name = re.sub(r'-+', '-', tech_name)  # Multiples guiones a uno
                tech_name = tech_name.strip('-')  # Quitar guiones al inicio/fin
                # Asegurar que no empiece con numero
                if tech_name and tech_name[0].isdigit():
                    tech_name = 'i-' + tech_name
                instance.technical_name = tech_name[:63]  # Limite K8s
            else:
                instance.technical_name = ''

    @api.depends('cluster_id', 'technical_name')
    def _compute_namespace(self):
        for instance in self:
            if instance.technical_name:
                instance.namespace = f"client-{instance.technical_name}"
            else:
                instance.namespace = ''

    @api.depends('subdomain', 'cluster_id.cloudflare_domain')
    def _compute_url(self):
        for instance in self:
            if instance.subdomain and instance.cluster_id and instance.cluster_id.cloudflare_domain:
                instance.url = f"https://{instance.subdomain}.{instance.cluster_id.cloudflare_domain}"
            else:
                instance.url = ''

    # ==================== DEFAULTS Y ONCHANGE ====================

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Buscar cluster por defecto
        default_cluster = self.env['k8s.cluster'].search([
            ('is_default', '=', True),
            ('state', '=', 'connected')
        ], limit=1)
        if default_cluster:
            res['cluster_id'] = default_cluster.id
        return res

    @api.onchange('plan_id')
    def _onchange_plan_id(self):
        """Copiar recursos del plan al cambiar"""
        if self.plan_id:
            self.odoo_image = self.plan_id.odoo_image
            self.cpu_limit = self.plan_id.resources_cpu_limit
            self.memory_limit = self.plan_id.resources_memory_limit
            self.storage_size = self.plan_id.storage_size

    @api.onchange('name')
    def _onchange_name(self):
        """Auto-generar subdominio del nombre"""
        if self.name and not self.subdomain:
            self.subdomain = self.technical_name

    # ==================== CREATE ====================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Generar nombre tecnico si no existe
            if vals.get('name') and not vals.get('technical_name'):
                name = vals['name']
                tech_name = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-'))
                tech_name = re.sub(r'-+', '-', tech_name).strip('-')
                if tech_name and tech_name[0].isdigit():
                    tech_name = 'i-' + tech_name
                vals['technical_name'] = tech_name[:63]

            tech_name = vals.get('technical_name', 'instance')

            # Auto-generar datos si no existen
            if not vals.get('subdomain'):
                vals['subdomain'] = tech_name

            if not vals.get('db_name'):
                vals['db_name'] = tech_name.replace('-', '_')

            if not vals.get('db_user'):
                vals['db_user'] = vals['db_name']

            if not vals.get('db_password'):
                vals['db_password'] = secrets.token_urlsafe(24)

            if not vals.get('admin_password'):
                vals['admin_password'] = secrets.token_urlsafe(16)

            # Copiar recursos del plan si no estan definidos
            if vals.get('plan_id'):
                plan = self.env['k8s.instance.plan'].browse(vals['plan_id'])
                if not vals.get('odoo_image'):
                    vals['odoo_image'] = plan.odoo_image
                if not vals.get('cpu_limit'):
                    vals['cpu_limit'] = plan.resources_cpu_limit
                if not vals.get('memory_limit'):
                    vals['memory_limit'] = plan.resources_memory_limit
                if not vals.get('storage_size'):
                    vals['storage_size'] = plan.storage_size

        return super().create(vals_list)

    # ==================== FLUJO PRINCIPAL ====================

    def action_create_instance(self):
        """Crear la instancia en Kubernetes - FLUJO PRINCIPAL"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Solo se pueden crear instancias en estado Borrador.'))

        if not self.managed_by_us:
            raise UserError(_('Esta instancia no es administrada por nosotros.'))

        if not self.cluster_id or self.cluster_id.state != 'connected':
            raise UserError(_('El cluster no esta conectado.'))

        if not self.plan_id:
            raise UserError(_('Debe seleccionar un plan.'))

        self.write({'state': 'creating', 'error_message': False})

        try:
            # PASO 1: Crear base de datos
            self._step_create_database()

            # PASO 2: Crear namespace
            self._step_create_namespace()

            # PASO 3: Aplicar manifiestos del plan
            self._step_apply_manifests()

            # PASO 4: Actualizar Cloudflare
            self._step_update_cloudflare()

            # PASO 5: Finalizar
            self.write({
                'state': 'running',
                'created_date': fields.Datetime.now(),
                'error_message': False,
            })

            self.message_post(body=_(
                'Instancia creada exitosamente.<br/>'
                'URL: <a href="%s">%s</a><br/>'
                'Usuario: admin<br/>'
                'Password: %s'
            ) % (self.url, self.url, self.admin_password))

            return self._notify_success(_('Instancia creada exitosamente.'))

        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            self.message_post(body=_('Error creando instancia: %s') % str(e))
            _logger.error(f"Error creating instance {self.name}: {e}")
            raise UserError(_('Error creando instancia: %s') % str(e))

    def _step_create_database(self):
        """Paso 1: Crear base de datos PostgreSQL"""
        _logger.info(f"Step 1: Creating database {self.db_name}")

        self.cluster_id.create_database(
            self.db_name,
            self.db_user,
            self.db_password
        )

        self.message_post(body=_('Base de datos creada: %s') % self.db_name)

    def _step_create_namespace(self):
        """Paso 2: Crear namespace en Kubernetes"""
        _logger.info(f"Step 2: Creating namespace {self.namespace}")

        if not K8S_AVAILABLE:
            raise UserError(_('Libreria kubernetes no disponible.'))

        core_api, _ = self.cluster_id._get_k8s_client()

        # Verificar si namespace existe
        try:
            core_api.read_namespace(name=self.namespace)
            _logger.info(f"Namespace {self.namespace} already exists")
        except ApiException as e:
            if e.status == 404:
                # Crear namespace
                namespace_body = client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=self.namespace,
                        labels={
                            'app': 'odoo-saas',
                            'instance': self.technical_name,
                            'managed-by': 'k8s-saas',
                        }
                    )
                )
                core_api.create_namespace(body=namespace_body)
                _logger.info(f"Created namespace {self.namespace}")
            else:
                raise

        self.message_post(body=_('Namespace creado: %s') % self.namespace)

    def _step_apply_manifests(self):
        """Paso 3: Aplicar manifiestos del plan"""
        _logger.info(f"Step 3: Applying manifests for plan {self.plan_id.name}")

        if not YAML_AVAILABLE:
            raise UserError(_('PyYAML no esta instalado.'))

        # Obtener templates ordenados
        templates = self.plan_id.get_manifest_templates(self.cluster_id.id)

        if not templates:
            raise UserError(_('El plan no tiene manifiestos configurados.'))

        # Preparar variables para renderizar
        variables = self._get_manifest_variables()

        for template in templates:
            self._apply_template(template, variables)

    def _get_manifest_variables(self):
        """Obtener diccionario de variables para renderizar manifiestos"""
        return {
            # Instancia
            'instance_name': self.technical_name,
            'namespace': self.namespace,
            'subdomain': self.subdomain,
            # Base de datos
            'db_host': self.cluster_id.db_host,
            'db_port': str(self.cluster_id.db_port or 5432),
            'db_name': self.db_name,
            'db_user': self.db_user,
            'db_password': self.db_password,
            # Odoo
            'admin_password': self.admin_password,
            'odoo_image': self.odoo_image or 'odoo:19.0',
            # Recursos
            'cpu_limit': self.cpu_limit or '2000m',
            'cpu_request': '500m',
            'memory_limit': self.memory_limit or '4Gi',
            'memory_request': '1Gi',
            'storage_size': self.storage_size or '20Gi',
            # Cloudflare
            'cloudflare_domain': self.cluster_id.cloudflare_domain or '',
        }

    def _apply_template(self, template, variables):
        """Aplicar un template de manifiesto"""
        _logger.info(f"Applying template: {template.name} ({template.manifest_type})")

        # Renderizar YAML
        yaml_rendered = template.render_yaml(variables)

        # Aplicar el manifiesto
        self._apply_single_manifest(yaml_rendered, template.manifest_type)

        # Guardar en historico
        self.env['k8s.instance.manifest'].create({
            'instance_id': self.id,
            'template_id': template.id,
            'manifest_type': template.manifest_type,
            'yaml_applied': yaml_rendered,
            'k8s_resource_name': self._extract_resource_name(yaml_rendered),
            'k8s_namespace': self.namespace,
            'state': 'applied',
            'applied_date': fields.Datetime.now(),
        })

        # Actualizar nombres de recursos
        if template.manifest_type == 'deployment':
            self.deployment_name = self._extract_resource_name(yaml_rendered)
        elif template.manifest_type == 'service':
            self.service_name = self._extract_resource_name(yaml_rendered)
        elif template.manifest_type == 'pvc':
            self.pvc_name = self._extract_resource_name(yaml_rendered)

    def _apply_single_manifest(self, yaml_content, manifest_type):
        """Aplicar un manifiesto YAML al cluster"""
        core_api, apps_api = self.cluster_id._get_k8s_client()

        # Parsear YAML (puede tener multiples documentos)
        docs = list(yaml.safe_load_all(yaml_content))

        for doc in docs:
            if not doc:
                continue

            kind = doc.get('kind', '').lower()
            metadata = doc.get('metadata', {})
            name = metadata.get('name')
            namespace = metadata.get('namespace', self.namespace)

            _logger.info(f"Applying {kind}: {name} in {namespace}")

            try:
                if kind == 'namespace':
                    try:
                        core_api.create_namespace(body=doc)
                    except ApiException as e:
                        if e.status != 409:  # Ignore "already exists"
                            raise

                elif kind == 'persistentvolumeclaim':
                    try:
                        core_api.create_namespaced_persistent_volume_claim(
                            namespace=namespace,
                            body=doc
                        )
                    except ApiException as e:
                        if e.status != 409:
                            raise

                elif kind == 'configmap':
                    try:
                        core_api.create_namespaced_config_map(
                            namespace=namespace,
                            body=doc
                        )
                    except ApiException as e:
                        if e.status != 409:
                            raise

                elif kind == 'secret':
                    try:
                        core_api.create_namespaced_secret(
                            namespace=namespace,
                            body=doc
                        )
                    except ApiException as e:
                        if e.status != 409:
                            raise

                elif kind == 'deployment':
                    try:
                        apps_api.create_namespaced_deployment(
                            namespace=namespace,
                            body=doc
                        )
                    except ApiException as e:
                        if e.status == 409:  # Already exists, update
                            apps_api.replace_namespaced_deployment(
                                name=name,
                                namespace=namespace,
                                body=doc
                            )
                        else:
                            raise

                elif kind == 'service':
                    try:
                        core_api.create_namespaced_service(
                            namespace=namespace,
                            body=doc
                        )
                    except ApiException as e:
                        if e.status != 409:
                            raise

                else:
                    _logger.warning(f"Unknown resource kind: {kind}")

            except Exception as e:
                _logger.error(f"Error applying {kind} {name}: {e}")
                raise

    def _extract_resource_name(self, yaml_content):
        """Extraer nombre del recurso del YAML"""
        try:
            doc = yaml.safe_load(yaml_content)
            return doc.get('metadata', {}).get('name', '')
        except:
            return ''

    def _step_update_cloudflare(self):
        """Paso 4: Actualizar configuracion de Cloudflare"""
        _logger.info(f"Step 4: Updating Cloudflare config")

        if not self.cluster_id.cloudflare_enabled:
            _logger.info("Cloudflare not enabled, skipping")
            return

        self.cluster_id.update_cloudflare_config(
            subdomain=self.subdomain,
            service_name=self.service_name or f"{self.technical_name}-svc",
            service_namespace=self.namespace,
            action='add'
        )

        self.message_post(body=_('Cloudflare configurado: %s') % self.url)

    # ==================== ACCIONES ====================

    def action_stop_instance(self):
        """Detener instancia (scale to 0)"""
        self.ensure_one()

        if self.state != 'running':
            raise UserError(_('Solo se pueden detener instancias en ejecucion.'))

        try:
            _, apps_api = self.cluster_id._get_k8s_client()

            if self.deployment_name:
                apps_api.patch_namespaced_deployment_scale(
                    name=self.deployment_name,
                    namespace=self.namespace,
                    body={'spec': {'replicas': 0}}
                )

            self.write({'state': 'stopped'})
            self.message_post(body=_('Instancia detenida.'))

            return self._notify_success(_('Instancia detenida.'))

        except Exception as e:
            raise UserError(_('Error deteniendo instancia: %s') % str(e))

    def action_start_instance(self):
        """Iniciar instancia (scale to 1)"""
        self.ensure_one()

        if self.state != 'stopped':
            raise UserError(_('Solo se pueden iniciar instancias detenidas.'))

        try:
            _, apps_api = self.cluster_id._get_k8s_client()

            if self.deployment_name:
                apps_api.patch_namespaced_deployment_scale(
                    name=self.deployment_name,
                    namespace=self.namespace,
                    body={'spec': {'replicas': 1}}
                )

            self.write({'state': 'running'})
            self.message_post(body=_('Instancia iniciada.'))

            return self._notify_success(_('Instancia iniciada.'))

        except Exception as e:
            raise UserError(_('Error iniciando instancia: %s') % str(e))

    def action_restart_instance(self):
        """Reiniciar instancia"""
        self.ensure_one()

        if self.state != 'running':
            raise UserError(_('Solo se pueden reiniciar instancias en ejecucion.'))

        try:
            _, apps_api = self.cluster_id._get_k8s_client()

            if self.deployment_name:
                # Forzar restart con annotation
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
                    name=self.deployment_name,
                    namespace=self.namespace,
                    body=patch
                )

            self.message_post(body=_('Instancia reiniciada.'))

            return self._notify_success(_('Instancia reiniciada.'))

        except Exception as e:
            raise UserError(_('Error reiniciando instancia: %s') % str(e))

    def action_delete_instance(self):
        """Eliminar instancia del cluster"""
        self.ensure_one()

        if self.state not in ('running', 'stopped', 'error'):
            raise UserError(_('No se puede eliminar esta instancia.'))

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Eliminar deployment
            if self.deployment_name:
                try:
                    apps_api.delete_namespaced_deployment(
                        name=self.deployment_name,
                        namespace=self.namespace
                    )
                except ApiException as e:
                    if e.status != 404:
                        _logger.warning(f"Error deleting deployment: {e}")

            # Eliminar service
            if self.service_name:
                try:
                    core_api.delete_namespaced_service(
                        name=self.service_name,
                        namespace=self.namespace
                    )
                except ApiException as e:
                    if e.status != 404:
                        _logger.warning(f"Error deleting service: {e}")

            # Eliminar PVC
            if self.pvc_name:
                try:
                    core_api.delete_namespaced_persistent_volume_claim(
                        name=self.pvc_name,
                        namespace=self.namespace
                    )
                except ApiException as e:
                    if e.status != 404:
                        _logger.warning(f"Error deleting PVC: {e}")

            # Eliminar namespace
            try:
                core_api.delete_namespace(name=self.namespace)
            except ApiException as e:
                if e.status != 404:
                    _logger.warning(f"Error deleting namespace: {e}")

            # Eliminar ruta de Cloudflare
            if self.cluster_id.cloudflare_enabled:
                try:
                    self.cluster_id.update_cloudflare_config(
                        subdomain=self.subdomain,
                        service_name=self.service_name,
                        service_namespace=self.namespace,
                        action='remove'
                    )
                except Exception as e:
                    _logger.warning(f"Error removing Cloudflare route: {e}")

            # Eliminar base de datos
            try:
                self.cluster_id.drop_database(self.db_name, self.db_user)
            except Exception as e:
                _logger.warning(f"Error dropping database: {e}")

            # Actualizar manifiestos aplicados
            self.applied_manifest_ids.write({'state': 'deleted'})

            self.write({'state': 'deleted'})
            self.message_post(body=_('Instancia eliminada del cluster.'))

            return self._notify_success(_('Instancia eliminada.'))

        except Exception as e:
            raise UserError(_('Error eliminando instancia: %s') % str(e))

    def action_refresh_status(self):
        """Actualizar estado desde Kubernetes"""
        self.ensure_one()

        if not self.deployment_name:
            return

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Obtener estado del deployment
            try:
                deployment = apps_api.read_namespaced_deployment(
                    name=self.deployment_name,
                    namespace=self.namespace
                )

                replicas = deployment.status.ready_replicas or 0
                if replicas > 0:
                    self.state = 'running'
                    self.pod_status = f'{replicas} pod(s) running'
                else:
                    self.state = 'stopped'
                    self.pod_status = 'No pods running'

            except ApiException as e:
                if e.status == 404:
                    self.state = 'deleted'
                    self.pod_status = 'Not found'
                else:
                    raise

            # Obtener estado del pod
            try:
                pods = core_api.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f'instance={self.technical_name}'
                )
                if pods.items:
                    pod = pods.items[0]
                    self.pod_status = pod.status.phase
            except:
                pass

        except Exception as e:
            self.error_message = str(e)
            _logger.error(f"Error refreshing instance {self.name}: {e}")

    def action_open_url(self):
        """Abrir URL de la instancia"""
        self.ensure_one()
        if not self.url:
            raise UserError(_('La instancia no tiene URL configurada.'))

        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    def action_view_manifests(self):
        """Ver manifiestos aplicados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manifiestos de %s') % self.name,
            'res_model': 'k8s.instance.manifest',
            'view_mode': 'list,form',
            'domain': [('instance_id', '=', self.id)],
            'context': {'default_instance_id': self.id},
        }

    def _delete_single_manifest(self, resource_name, namespace, manifest_type):
        """Eliminar un recurso individual del cluster"""
        core_api, apps_api = self.cluster_id._get_k8s_client()

        try:
            if manifest_type == 'deployment':
                apps_api.delete_namespaced_deployment(name=resource_name, namespace=namespace)
            elif manifest_type == 'service':
                core_api.delete_namespaced_service(name=resource_name, namespace=namespace)
            elif manifest_type == 'pvc':
                core_api.delete_namespaced_persistent_volume_claim(name=resource_name, namespace=namespace)
            elif manifest_type == 'configmap':
                core_api.delete_namespaced_config_map(name=resource_name, namespace=namespace)
            elif manifest_type == 'secret':
                core_api.delete_namespaced_secret(name=resource_name, namespace=namespace)
        except ApiException as e:
            if e.status != 404:
                raise

    def _notify_success(self, message):
        """Mostrar notificacion de exito"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Exito'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    # ==================== CRON ====================

    @api.model
    def cron_refresh_all_instances(self):
        """Cron para actualizar estado de todas las instancias"""
        instances = self.search([
            ('state', 'in', ('running', 'stopped', 'creating')),
            ('managed_by_us', '=', True)
        ])
        for instance in instances:
            try:
                instance.action_refresh_status()
            except Exception as e:
                _logger.error(f"Error refreshing instance {instance.name}: {e}")
