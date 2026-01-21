import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class K8sInstanceManifest(models.Model):
    _name = 'k8s.instance.manifest'
    _description = 'Manifiesto Aplicado a Instancia'
    _order = 'applied_date desc, id desc'

    name = fields.Char('Nombre', compute='_compute_name', store=True)

    instance_id = fields.Many2one(
        'k8s.instance',
        string='Instancia',
        required=True,
        ondelete='cascade',
        index=True
    )
    template_id = fields.Many2one(
        'k8s.manifest.template',
        string='Template Origen',
        ondelete='set null'
    )

    # Tipo heredado del template
    manifest_type = fields.Selection([
        ('namespace', 'Namespace'),
        ('pvc', 'PersistentVolumeClaim'),
        ('configmap', 'ConfigMap'),
        ('secret', 'Secret'),
        ('deployment', 'Deployment'),
        ('service', 'Service'),
        ('ingress', 'Ingress'),
        ('cloudflare', 'Cloudflare Config'),
        ('other', 'Otro'),
    ], string='Tipo', required=True)

    # YAML aplicado (con variables ya resueltas)
    yaml_applied = fields.Text('YAML Aplicado', required=True)

    # Recurso en K8s
    k8s_resource_name = fields.Char('Nombre Recurso K8s')
    k8s_namespace = fields.Char('Namespace')

    # Fechas y estado
    applied_date = fields.Datetime('Fecha Aplicacion', default=fields.Datetime.now)
    deleted_date = fields.Datetime('Fecha Eliminacion')

    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('applied', 'Aplicado'),
        ('deleted', 'Eliminado'),
        ('error', 'Error'),
    ], string='Estado', default='pending', required=True)

    error_message = fields.Text('Mensaje de Error')

    @api.depends('instance_id', 'manifest_type', 'k8s_resource_name')
    def _compute_name(self):
        for record in self:
            parts = []
            if record.instance_id:
                parts.append(record.instance_id.name)
            if record.manifest_type:
                parts.append(record.manifest_type)
            if record.k8s_resource_name:
                parts.append(record.k8s_resource_name)
            record.name = ' - '.join(parts) if parts else 'Nuevo'

    def action_reapply(self):
        """Re-aplicar este manifiesto al cluster"""
        self.ensure_one()

        if not self.instance_id or not self.instance_id.cluster_id:
            raise UserError(_('La instancia no tiene cluster asignado.'))

        try:
            self.instance_id._apply_single_manifest(self.yaml_applied, self.manifest_type)
            self.write({
                'state': 'applied',
                'applied_date': fields.Datetime.now(),
                'error_message': False,
            })
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise UserError(_('Error al re-aplicar manifiesto: %s') % str(e))

    def action_delete_from_cluster(self):
        """Eliminar este recurso del cluster"""
        self.ensure_one()

        if not self.instance_id or not self.instance_id.cluster_id:
            raise UserError(_('La instancia no tiene cluster asignado.'))

        if self.state == 'deleted':
            raise UserError(_('El recurso ya fue eliminado.'))

        try:
            self.instance_id._delete_single_manifest(
                self.k8s_resource_name,
                self.k8s_namespace,
                self.manifest_type
            )
            self.write({
                'state': 'deleted',
                'deleted_date': fields.Datetime.now(),
            })
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise UserError(_('Error al eliminar recurso: %s') % str(e))

    def action_view_yaml(self):
        """Ver el YAML aplicado en un popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('YAML - %s') % self.name,
            'res_model': 'k8s.instance.manifest',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }
