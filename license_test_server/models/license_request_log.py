from odoo import models, fields
import json


class LicenseRequestLog(models.Model):
    _name = 'license.request.log'
    _description = 'Log de Solicitudes de Licencia'
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        default=lambda self: self.env['ir.sequence'].next_by_code('license.request.log') or 'REQ-000'
    )
    request_date = fields.Datetime(
        string='Fecha de Solicitud',
        default=fields.Datetime.now,
        readonly=True
    )

    # === DATOS RECIBIDOS ===
    db_uuid = fields.Char(string='UUID de BD', readonly=True)
    db_name = fields.Char(string='Nombre de BD', readonly=True)
    nbr_users = fields.Integer(string='Total Usuarios', readonly=True)
    nbr_active_users = fields.Integer(string='Usuarios Activos', readonly=True)
    nbr_share_users = fields.Integer(string='Usuarios Portal', readonly=True)
    enterprise_code_received = fields.Char(string='Código Recibido', readonly=True)
    odoo_version = fields.Char(string='Versión Odoo', readonly=True)
    web_base_url = fields.Char(string='URL Base', readonly=True)
    apps_installed = fields.Text(string='Módulos Instalados', readonly=True)

    # === DATOS COMPLETOS ===
    raw_request = fields.Text(string='Solicitud Raw', readonly=True)
    raw_response = fields.Text(string='Respuesta Raw', readonly=True)

    # === ESTADO ===
    state = fields.Selection([
        ('success', 'Éxito'),
        ('error', 'Error'),
        ('simulated_error', 'Error Simulado'),
    ], string='Estado', default='success', readonly=True)

    ip_address = fields.Char(string='IP de Origen', readonly=True)

    def _parse_request_data(self, data):
        """Parsear los datos de la solicitud"""
        try:
            if isinstance(data, str):
                data = eval(data)  # Odoo envía como string de dict

            return {
                'db_uuid': data.get('dbuuid', ''),
                'db_name': data.get('dbname', ''),
                'nbr_users': data.get('nbr_users', 0),
                'nbr_active_users': data.get('nbr_active_users', 0),
                'nbr_share_users': data.get('nbr_share_users', 0),
                'enterprise_code_received': data.get('enterprise_code', ''),
                'odoo_version': data.get('version', ''),
                'web_base_url': data.get('web_base_url', ''),
                'apps_installed': json.dumps(data.get('apps', []), indent=2),
                'raw_request': json.dumps(data, indent=2, default=str),
            }
        except Exception as e:
            return {
                'raw_request': str(data),
                'state': 'error',
            }
