import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sInstance(models.Model):
    _name = 'k8s.instance'
    _description = 'Instancia Odoo en Kubernetes'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Nombre', required=True, tracking=True)
    technical_name = fields.Char(
        'Nombre Técnico',
        compute='_compute_technical_name',
        store=True
    )

    cluster_id = fields.Many2one(
        'k8s.cluster',
        string='Cluster',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    namespace = fields.Char(
        'Namespace',
        compute='_compute_namespace',
        store=True
    )

    # Customer
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True
    )
    subscription_id = fields.Many2one(
        'sale.order',
        string='Suscripción',
        domain=[('is_subscription', '=', True)]
    )

    # Database
    db_name = fields.Char('Base de Datos', tracking=True)
    db_user = fields.Char('Usuario DB')
    db_password = fields.Char('Password DB')

    # Access
    subdomain = fields.Char('Subdominio', tracking=True)
    url = fields.Char('URL', compute='_compute_url', store=True)

    # Status
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('creating', 'Creando'),
        ('running', 'Ejecutando'),
        ('stopped', 'Detenido'),
        ('error', 'Error'),
        ('deleted', 'Eliminado'),
    ], string='Estado', default='draft', tracking=True, required=True)

    # K8s Resources
    deployment_name = fields.Char('Deployment Name')
    service_name = fields.Char('Service Name')
    pod_status = fields.Char('Pod Status')

    # Resources
    odoo_version = fields.Char('Versión Odoo', default='19.0')
    workers = fields.Integer('Workers', default=2)
    memory_limit = fields.Char('Límite Memoria', default='2Gi')
    cpu_limit = fields.Char('Límite CPU', default='1000m')

    # Dates
    created_date = fields.Datetime('Fecha de Creación')
    last_accessed = fields.Datetime('Último Acceso')

    # Error tracking
    error_message = fields.Text('Mensaje de Error')

    @api.depends('name')
    def _compute_technical_name(self):
        for instance in self:
            if instance.name:
                # Convert to lowercase, remove special chars, replace spaces with dashes
                tech_name = re.sub(r'[^a-z0-9-]', '', instance.name.lower().replace(' ', '-'))
                # Ensure it doesn't start with a number
                if tech_name and tech_name[0].isdigit():
                    tech_name = 'i-' + tech_name
                instance.technical_name = tech_name[:63]  # K8s name limit
            else:
                instance.technical_name = ''

    @api.depends('cluster_id', 'cluster_id.default_namespace')
    def _compute_namespace(self):
        for instance in self:
            instance.namespace = instance.cluster_id.default_namespace if instance.cluster_id else 'default'

    @api.depends('subdomain', 'cluster_id.cloudflare_zone')
    def _compute_url(self):
        for instance in self:
            if instance.subdomain and instance.cluster_id.cloudflare_zone:
                instance.url = f"https://{instance.subdomain}.{instance.cluster_id.cloudflare_zone}"
            else:
                instance.url = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('db_name') and vals.get('technical_name'):
                vals['db_name'] = vals['technical_name'].replace('-', '_')
            if not vals.get('db_user'):
                vals['db_user'] = vals.get('db_name', 'odoo')
            if not vals.get('db_password'):
                import secrets
                vals['db_password'] = secrets.token_urlsafe(16)
            if not vals.get('subdomain') and vals.get('technical_name'):
                vals['subdomain'] = vals['technical_name']

        return super().create(vals_list)

    def action_create_instance(self):
        """Create the Kubernetes instance"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Solo se pueden crear instancias en estado Borrador.'))

        self.state = 'creating'

        try:
            # 1. Create database
            self.cluster_id.create_database(self.db_name, self.db_user)

            # 2. Get K8s client
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # 3. Generate deployment
            deployment, service = self.cluster_id.get_deployment_template(
                self.technical_name,
                self.db_name,
                self.subdomain
            )

            # 4. Create deployment in K8s
            from kubernetes.client.rest import ApiException

            try:
                apps_api.create_namespaced_deployment(
                    namespace=self.namespace,
                    body=deployment
                )
                self.deployment_name = self.technical_name
            except ApiException as e:
                if e.status == 409:  # Already exists
                    _logger.warning(f"Deployment {self.technical_name} already exists")
                else:
                    raise

            # 5. Create service
            try:
                core_api.create_namespaced_service(
                    namespace=self.namespace,
                    body=service
                )
                self.service_name = f'{self.technical_name}-svc'
            except ApiException as e:
                if e.status == 409:
                    _logger.warning(f"Service {self.technical_name}-svc already exists")
                else:
                    raise

            # 6. Update status
            self.write({
                'state': 'running',
                'created_date': fields.Datetime.now(),
                'error_message': False,
            })

            # 7. Configure Cloudflare tunnel (if available)
            # self._configure_cloudflare_tunnel()

            self.message_post(body=_('Instancia creada exitosamente.'))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Instancia Creada'),
                    'message': _('La instancia %s ha sido creada.') % self.name,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            _logger.error(f"Error creating instance {self.name}: {e}")
            raise UserError(_('Error creando instancia: %s') % str(e))

    def action_stop_instance(self):
        """Stop the Kubernetes instance (scale to 0)"""
        self.ensure_one()

        if self.state != 'running':
            raise UserError(_('Solo se pueden detener instancias en ejecución.'))

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Scale deployment to 0
            apps_api.patch_namespaced_deployment_scale(
                name=self.deployment_name,
                namespace=self.namespace,
                body={'spec': {'replicas': 0}}
            )

            self.state = 'stopped'
            self.message_post(body=_('Instancia detenida.'))

        except Exception as e:
            raise UserError(_('Error deteniendo instancia: %s') % str(e))

    def action_start_instance(self):
        """Start a stopped instance"""
        self.ensure_one()

        if self.state != 'stopped':
            raise UserError(_('Solo se pueden iniciar instancias detenidas.'))

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Scale deployment to 1
            apps_api.patch_namespaced_deployment_scale(
                name=self.deployment_name,
                namespace=self.namespace,
                body={'spec': {'replicas': 1}}
            )

            self.state = 'running'
            self.message_post(body=_('Instancia iniciada.'))

        except Exception as e:
            raise UserError(_('Error iniciando instancia: %s') % str(e))

    def action_delete_instance(self):
        """Delete the Kubernetes instance"""
        self.ensure_one()

        if self.state not in ('running', 'stopped', 'error'):
            raise UserError(_('No se puede eliminar esta instancia.'))

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Delete deployment
            if self.deployment_name:
                try:
                    apps_api.delete_namespaced_deployment(
                        name=self.deployment_name,
                        namespace=self.namespace
                    )
                except Exception:
                    pass

            # Delete service
            if self.service_name:
                try:
                    core_api.delete_namespaced_service(
                        name=self.service_name,
                        namespace=self.namespace
                    )
                except Exception:
                    pass

            self.state = 'deleted'
            self.message_post(body=_('Instancia eliminada del cluster.'))

        except Exception as e:
            raise UserError(_('Error eliminando instancia: %s') % str(e))

    def action_refresh_status(self):
        """Refresh the status from Kubernetes"""
        self.ensure_one()

        if not self.deployment_name:
            return

        try:
            core_api, apps_api = self.cluster_id._get_k8s_client()

            # Get deployment status
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

            # Get pod details
            pods = core_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f'instance={self.technical_name}'
            )

            if pods.items:
                pod = pods.items[0]
                self.pod_status = pod.status.phase

        except Exception as e:
            self.error_message = str(e)
            _logger.error(f"Error refreshing instance {self.name}: {e}")

    def action_open_url(self):
        """Open the instance URL in browser"""
        self.ensure_one()
        if not self.url:
            raise UserError(_('La instancia no tiene URL configurada.'))

        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    def cron_refresh_all_instances(self):
        """Cron job to refresh all instance statuses"""
        instances = self.search([('state', 'in', ('running', 'stopped', 'creating'))])
        for instance in instances:
            try:
                instance.action_refresh_status()
            except Exception as e:
                _logger.error(f"Error refreshing instance {instance.name}: {e}")
