from odoo import models, fields, api
from datetime import datetime, timedelta


class LicenseConfig(models.Model):
    _name = 'license.test.config'
    _description = 'Configuración de Respuesta de Licencia'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        default='Configuración Principal'
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Solo una configuración puede estar activa'
    )

    # === RESPUESTA DE LICENCIA ===
    expiration_date = fields.Datetime(
        string='Fecha de Expiración',
        default=lambda self: datetime.now() + timedelta(days=365),
        help='Fecha que se enviará como expiración de licencia'
    )
    expiration_reason = fields.Selection([
        ('trial', 'Trial (Prueba)'),
        ('demo', 'Demo'),
        ('renewal', 'Renewal (Renovación pagada)'),
        ('upsell', 'Upsell (Necesita más usuarios)'),
    ], string='Razón de Expiración', default='renewal')

    enterprise_code = fields.Char(
        string='Código Enterprise',
        default='TEST-LICENSE-CODE-001',
        help='Código de licencia a devolver'
    )

    # === SIMULACIÓN DE ERRORES ===
    simulate_error = fields.Boolean(
        string='Simular Error',
        default=False,
        help='Simular que el servidor no responde'
    )
    simulate_linked_db = fields.Boolean(
        string='Simular BD Ya Vinculada',
        default=False,
        help='Simular que el código ya está vinculado a otra BD'
    )
    linked_subscription_url = fields.Char(
        string='URL de Suscripción Vinculada',
        default='https://www.odoo.com/my/subscription/123'
    )
    linked_email = fields.Char(
        string='Email Vinculado',
        default='otro@empresa.com'
    )

    # === MENSAJES ===
    custom_message = fields.Text(
        string='Mensaje Personalizado',
        help='Mensaje que aparecerá en las notificaciones de Odoo'
    )

    # === ESTADÍSTICAS ===
    request_count = fields.Integer(
        string='Solicitudes Recibidas',
        readonly=True,
        default=0
    )
    last_request_date = fields.Datetime(
        string='Última Solicitud',
        readonly=True
    )

    @api.model
    def get_active_config(self):
        """Obtener la configuración activa"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            # Crear configuración por defecto
            config = self.create({
                'name': 'Configuración Principal',
                'active': True,
            })
        return config

    def get_response_dict(self):
        """Generar el diccionario de respuesta como lo haría Odoo"""
        self.ensure_one()

        # Incrementar contador
        self.sudo().write({
            'request_count': self.request_count + 1,
            'last_request_date': fields.Datetime.now(),
        })

        if self.simulate_error:
            return None

        response = {
            'messages': [],
            'enterprise_info': {
                'expiration_date': self.expiration_date.strftime('%Y-%m-%d %H:%M:%S') if self.expiration_date else False,
                'expiration_reason': self.expiration_reason,
                'enterprise_code': self.enterprise_code,
            }
        }

        # Agregar mensaje personalizado
        if self.custom_message:
            response['messages'].append(self.custom_message)

        # Simular BD ya vinculada
        if self.simulate_linked_db:
            response['enterprise_info']['database_already_linked_subscription_url'] = self.linked_subscription_url
            response['enterprise_info']['database_already_linked_email'] = self.linked_email
            response['enterprise_info']['database_already_linked_send_mail_url'] = 'https://www.odoo.com/help'

        return response

    def action_reset_counter(self):
        """Resetear contador de solicitudes"""
        self.write({
            'request_count': 0,
            'last_request_date': False,
        })
