import logging
import json
from ast import literal_eval

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LicenseTestController(http.Controller):

    @http.route('/publisher-warranty/', type='http', auth='none', methods=['POST'], csrf=False)
    def publisher_warranty(self, **kwargs):
        """
        Endpoint que simula services.odoo.com/publisher-warranty/

        Odoo envía:
        - arg0: string con dict de datos (uuid, users, modules, etc.)
        - action: "update"

        Debe responder con:
        {
            'messages': [],
            'enterprise_info': {
                'expiration_date': '2025-12-31 23:59:59',
                'expiration_reason': 'renewal',
                'enterprise_code': 'XXX',
                ...
            }
        }
        """
        _logger.info("=" * 60)
        _logger.info("SOLICITUD DE LICENCIA RECIBIDA")
        _logger.info("=" * 60)

        try:
            # Obtener datos de la solicitud
            arg0 = kwargs.get('arg0', '{}')
            action = kwargs.get('action', '')

            _logger.info(f"Action: {action}")
            _logger.info(f"Raw arg0: {arg0[:500]}...")  # Solo primeros 500 chars

            # Parsear los datos
            try:
                request_data = literal_eval(arg0) if arg0 else {}
            except:
                request_data = {'raw': arg0}

            _logger.info(f"Parsed data: {json.dumps(request_data, indent=2, default=str)[:1000]}")

            # Obtener configuración activa
            Config = request.env['license.test.config'].sudo()
            config = Config.get_active_config()

            # Crear log de la solicitud
            Log = request.env['license.request.log'].sudo()
            log_data = Log._parse_request_data(request_data)
            log_data['ip_address'] = request.httprequest.remote_addr

            # Generar respuesta
            response_dict = config.get_response_dict()

            if response_dict is None:
                # Simular error
                log_data['state'] = 'simulated_error'
                log_data['raw_response'] = 'ERROR SIMULADO'
                Log.create(log_data)
                return http.Response(
                    "Server Error",
                    status=500,
                    content_type='text/plain'
                )

            response_str = str(response_dict)
            log_data['raw_response'] = json.dumps(response_dict, indent=2, default=str)
            log_data['state'] = 'success'

            Log.create(log_data)

            _logger.info(f"Respuesta enviada: {response_str[:500]}")
            _logger.info("=" * 60)

            return http.Response(
                response_str,
                status=200,
                content_type='text/plain'
            )

        except Exception as e:
            _logger.error(f"Error procesando solicitud de licencia: {e}")

            # Intentar crear log de error
            try:
                Log = request.env['license.request.log'].sudo()
                Log.create({
                    'raw_request': str(kwargs),
                    'raw_response': str(e),
                    'state': 'error',
                    'ip_address': request.httprequest.remote_addr,
                })
            except:
                pass

            return http.Response(
                str({'error': str(e)}),
                status=500,
                content_type='text/plain'
            )

    @http.route('/publisher-warranty/test', type='http', auth='none', methods=['GET'], csrf=False)
    def test_endpoint(self, **kwargs):
        """Endpoint de prueba para verificar que el servidor funciona"""
        return http.Response(
            "License Test Server OK - Endpoint activo",
            status=200,
            content_type='text/plain'
        )
