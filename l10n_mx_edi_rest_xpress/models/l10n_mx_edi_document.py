# -*- coding: utf-8 -*-

import base64
import json
import logging
import requests
from cryptography.hazmat.primitives import serialization
from lxml import etree

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    # ===========================
    # PAC Method Map Extension
    # ===========================

    def _get_pac_method_map(self):
        """Extend PAC method map to include REST XPRESS."""
        res = super()._get_pac_method_map()
        res['credentials']['rest_xpress'] = self._get_rest_xpress_credentials
        res['sign']['rest_xpress'] = self._rest_xpress_sign
        res['cancel']['rest_xpress'] = self._rest_xpress_cancel
        return res

    # ===========================
    # REST XPRESS Helper: Get Unencrypted Private Key
    # ===========================

    @api.model
    def _get_unencrypted_private_key_pem(self, key_record):
        """
        Get the private key in PEM format without encryption.

        The certificate.key model stores the key in pem_key field (base64 encoded).
        If the key has a password, we need to load it and re-export without encryption.

        :param key_record: certificate.key record
        :return: bytes with PEM formatted private key (unencrypted)
        """
        key_record = key_record.sudo()
        pem_key_b64 = key_record.with_context(bin_size=False).pem_key

        if not pem_key_b64:
            raise UserError(_('No se encontró la llave privada en el certificado.'))

        # Decode the base64 encoded PEM key
        pem_key_bytes = base64.b64decode(pem_key_b64)

        # Get password if any
        password = key_record.password
        if password and not isinstance(password, bytes):
            password = password.encode('utf-8')

        # Load the private key
        try:
            private_key = serialization.load_pem_private_key(pem_key_bytes, password or None)
        except Exception as e:
            raise UserError(_('Error al cargar la llave privada: %s', str(e)))

        # Export the key without encryption (REST XPRESS needs unencrypted PEM)
        unencrypted_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        return unencrypted_pem

    # ===========================
    # REST XPRESS PAC Methods
    # ===========================

    @api.model
    def _get_rest_xpress_credentials(self, company):
        """
        Return company credentials for PAC: REST XPRESS.
        Does not depend on a recordset.

        :param company: res.company record
        :return: dict with credentials or error
        """
        if not company.l10n_mx_edi_pac_password:
            return {'errors': [_('REST XPRESS API Key is missing. Please configure it in Accounting Settings.')]}

        # REST XPRESS URLs según documentación oficial
        base_url = 'https://dev.timbradorxpress.mx' if company.l10n_mx_edi_pac_test_env else 'https://app.timbradorxpress.mx'

        return {
            'api_key': company.l10n_mx_edi_pac_password,
            'sign_url': f'{base_url}/api/rest/servicio/timbrarJSON',
            'cancel_url': f'{base_url}/api/rest/servicio/cancelarPEM',
            'status_url': f'{base_url}/api/rest/servicio/consultarEstadoSAT',
            'credits_url': f'{base_url}/api/rest/servicio/consultarCreditosDisponibles',
            'test_mode': company.l10n_mx_edi_pac_test_env,
        }

    @api.model
    def _rest_xpress_sign(self, credentials, cfdi):
        """
        Send the CFDI to REST XPRESS PAC for signature using timbrarJSON endpoint.
        Does not depend on a recordset.

        :param credentials: dict with api_key, sign_url
        :param cfdi: bytes with CFDI XML to sign
        :return: dict with cfdi_str (signed XML) or errors
        """
        try:
            # Get certificate - REST XPRESS needs it to sign internally
            # Unlike other PACs, REST XPRESS receives unsigned XML + certificate
            company = self.env.company
            certificate_sudo = company.sudo().l10n_mx_edi_certificate_ids.filtered('is_valid')[:1]
            if not certificate_sudo:
                return {'errors': [_('No valid certificate found for company %s', company.name)]}

            # Convert CFDI XML to REST XPRESS JSON format
            cfdi_json = self._rest_xpress_xml_to_json(cfdi, company)
            if not cfdi_json:
                return {'errors': [_('Failed to convert CFDI XML to JSON format')]}

            # Encode JSON to base64
            json_str = json.dumps(cfdi_json, ensure_ascii=False, indent=None)
            json_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

            # Get certificate and key in PEM format
            cer_pem = base64.b64decode(certificate_sudo.pem_certificate).decode('utf-8')
            key_pem = self._get_unencrypted_private_key_pem(certificate_sudo.private_key_id).decode('utf-8')

            # Prepare request payload
            payload = {
                'apikey': credentials['api_key'],
                'jsonB64': json_b64,
                'cerPEM': cer_pem,
                'keyPEM': key_pem,
            }

            # ============= DEBUG LOGS =============
            _logger.info('=' * 60)
            _logger.info('REST XPRESS DEBUG - REQUEST')
            _logger.info('=' * 60)
            _logger.info('URL: %s', credentials['sign_url'])
            _logger.info('API Key (first 8 chars): %s...', credentials['api_key'][:8] if credentials['api_key'] else 'EMPTY')
            _logger.info('Test Mode: %s', credentials.get('test_mode'))

            # Decode and log JSON content
            try:
                json_decoded = base64.b64decode(json_b64).decode('utf-8')
                _logger.info('JSON Content (decoded from base64):')
                _logger.info('%s', json_decoded)
            except Exception as e:
                _logger.error('Could not decode JSON: %s', e)

            _logger.info('Certificate PEM length: %d chars', len(cer_pem) if cer_pem else 0)
            _logger.info('Key PEM length: %d chars', len(key_pem) if key_pem else 0)
            _logger.info('=' * 60)
            # ============= END DEBUG =============

            # Call REST XPRESS API
            _logger.info('REST XPRESS: Sending CFDI to %s', credentials['sign_url'])
            response = requests.post(
                credentials['sign_url'],
                data=payload,
                timeout=30
            )

            # ============= DEBUG RESPONSE =============
            _logger.info('REST XPRESS DEBUG - RESPONSE')
            _logger.info('Status Code: %s', response.status_code)
            _logger.info('Response Text: %s', response.text[:2000] if response.text else 'EMPTY')
            _logger.info('=' * 60)
            # ============= END DEBUG =============

            # Parse response
            return self._rest_xpress_parse_sign_response(response)

        except requests.exceptions.Timeout:
            return {'errors': [_('REST XPRESS timeout: The service took too long to respond')]}
        except requests.exceptions.RequestException as e:
            return {'errors': [_('REST XPRESS connection error: %s', str(e))]}
        except Exception as e:
            _logger.error('REST XPRESS sign error: %s', str(e), exc_info=True)
            return {'errors': [_('REST XPRESS unexpected error: %s', str(e))]}

    @api.model
    def _rest_xpress_cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """
        Cancel CFDI using REST XPRESS PAC via cancelarPEM endpoint.
        Does not depend on a recordset.

        :param cfdi_values: dict with company and certificate data
        :param credentials: dict with api_key, cancel_url
        :param uuid: str with UUID to cancel
        :param cancel_reason: str with cancellation reason ('01', '02', '03', '04')
        :param cancel_uuid: str with replacement UUID (optional, for reason '01')
        :return: dict with success True or errors
        """
        try:
            # Get certificate from cfdi_values (same as other PACs)
            certificate_sudo = cfdi_values.get('certificate')
            if not certificate_sudo:
                return {'errors': [_('No certificate found in cfdi_values')]}

            company = cfdi_values.get('root_company')
            if not company:
                return {'errors': [_('No company found in cfdi_values')]}

            # Get RFC receptor and total from the CFDI document
            # Search for the l10n_mx_edi.document with this UUID to get the attachment
            rfc_receptor = ''
            total = '0.00'

            edi_document = self.env['l10n_mx_edi.document'].search([
                ('attachment_uuid', '=', uuid)
            ], limit=1)

            if edi_document and edi_document.attachment_id:
                # Decode the CFDI attachment to extract RFC receptor and total
                cfdi_data = edi_document.attachment_id.raw
                if cfdi_data:
                    cfdi_infos = self._decode_cfdi_attachment(cfdi_data)
                    rfc_receptor = cfdi_infos.get('customer_rfc', '')
                    total = cfdi_infos.get('amount_total', '0.00')
                    _logger.info('REST XPRESS: Extracted from CFDI - RFC Receptor: %s, Total: %s', rfc_receptor, total)

            if not rfc_receptor or not total or total == '0.00':
                _logger.warning('REST XPRESS: Could not extract RFC receptor or total from CFDI document for UUID %s', uuid)

            # Get certificate and key in PEM format
            certificate_sudo = certificate_sudo.sudo()
            cer_pem = base64.b64decode(certificate_sudo.pem_certificate).decode('utf-8')
            key_pem = self._get_unencrypted_private_key_pem(certificate_sudo.private_key_id).decode('utf-8')

            # Prepare cancellation request for cancelarPEM endpoint
            # According to documentation page 15
            payload = {
                'apikey': credentials['api_key'],
                'keyPEM': key_pem,
                'cerPEM': cer_pem,
                'uuid': uuid,
                'rfcEmisor': company.vat,
                'rfcReceptor': rfc_receptor,
                'total': str(total),
                'motivo': cancel_reason,
                'folioSustitucion': cancel_uuid or '',
            }

            # ============= DEBUG LOGS =============
            _logger.info('=' * 60)
            _logger.info('REST XPRESS DEBUG - CANCEL REQUEST')
            _logger.info('=' * 60)
            _logger.info('URL: %s', credentials['cancel_url'])
            _logger.info('UUID: %s', uuid)
            _logger.info('RFC Emisor: %s', company.vat)
            _logger.info('RFC Receptor: %s', rfc_receptor)
            _logger.info('Total: %s', total)
            _logger.info('Motivo: %s', cancel_reason)
            _logger.info('Folio Sustitucion: %s', cancel_uuid or '(empty)')
            _logger.info('=' * 60)
            # ============= END DEBUG =============

            # Call REST XPRESS cancellation API
            _logger.info('REST XPRESS: Cancelling CFDI %s', uuid)
            response = requests.post(
                credentials['cancel_url'],
                data=payload,
                timeout=30
            )

            # ============= DEBUG RESPONSE =============
            _logger.info('REST XPRESS DEBUG - CANCEL RESPONSE')
            _logger.info('Status Code: %s', response.status_code)
            _logger.info('Response Text: %s', response.text[:2000] if response.text else 'EMPTY')
            _logger.info('=' * 60)
            # ============= END DEBUG =============

            # Parse response
            return self._rest_xpress_parse_cancel_response(response)

        except requests.exceptions.Timeout:
            return {'errors': [_('REST XPRESS timeout: The service took too long to respond')]}
        except requests.exceptions.RequestException as e:
            return {'errors': [_('REST XPRESS connection error: %s', str(e))]}
        except Exception as e:
            _logger.error('REST XPRESS cancel error: %s', str(e), exc_info=True)
            return {'errors': [_('REST XPRESS unexpected error: %s', str(e))]}

    # ===========================
    # REST XPRESS Helper Methods
    # ===========================

    @api.model
    def _rest_xpress_parse_sign_response(self, response):
        """
        Parse REST XPRESS sign response.

        :param response: requests.Response object
        :return: dict with cfdi_str (signed CFDI XML bytes) or errors
        """
        try:
            response.raise_for_status()
            data = response.json()

            # Log response for debugging
            _logger.info('REST XPRESS response: code=%s, message=%s, has_data=%s',
                        data.get('code'), data.get('message'), bool(data.get('data')))

            # Check response code (200 = success)
            code = data.get('code')
            if code != '200' and code != 200:
                error_msg = data.get('message', 'Unknown error')
                return {'errors': [_('REST XPRESS error (code %s): %s', code, error_msg)]}

            # Extract signed CFDI XML from 'data' field
            cfdi_signed = data.get('data')
            if not cfdi_signed:
                return {'errors': [_('REST XPRESS did not return signed CFDI in data field')]}

            # REST XPRESS returns XML as string (not base64)
            if isinstance(cfdi_signed, str):
                cfdi_bytes = cfdi_signed.encode('utf-8')
            else:
                cfdi_bytes = cfdi_signed

            return {
                'cfdi_str': cfdi_bytes,
            }

        except ValueError:
            # Response is not JSON
            return {'errors': [_('REST XPRESS returned invalid response: %s', response.text[:200])]}

    @api.model
    def _rest_xpress_parse_cancel_response(self, response):
        """
        Parse REST XPRESS cancel response.

        Response codes according to documentation (page 27):
        - 201: UUID Cancelado exitosamente
        - 202: UUID Previamente cancelado
        - 203: UUID No corresponde el RFC del emisor
        - 205: UUID No existe

        :param response: requests.Response object
        :return: dict with empty dict on success or errors list
        """
        try:
            response.raise_for_status()
            data = response.json()

            _logger.info('REST XPRESS cancel response parsed: %s', data)

            # Get response code
            code = str(data.get('code', ''))
            message = data.get('message', '')

            # Success codes - return empty dict like other PACs (Finkok)
            if code == '201':
                _logger.info('REST XPRESS: Cancelación exitosa (code 201)')
                return {}  # Empty dict = success

            if code == '202':
                _logger.info('REST XPRESS: UUID previamente cancelado (code 202)')
                return {}  # Empty dict = success

            # Error codes - return errors list
            if code == '203':
                error_msg = _('Error de cancelación REST XPRESS (código 203): El RFC del emisor no corresponde con el CFDI. Verifique que el certificado corresponda al emisor del CFDI.')
                _logger.error(error_msg)
                return {'errors': [error_msg]}

            if code == '205':
                error_msg = _('Error de cancelación REST XPRESS (código 205): El UUID no existe en el SAT. Esto puede ocurrir si el CFDI fue emitido en un ambiente diferente (pruebas vs producción) o si aún no ha sido procesado por el SAT.')
                _logger.error(error_msg)
                return {'errors': [error_msg]}

            # Handle other error codes
            if code.startswith('CA'):
                error_msg = _('Error de cancelación REST XPRESS (código %s): %s', code, message or 'Error no especificado')
                _logger.error(error_msg)
                return {'errors': [error_msg]}

            # Generic error with message
            if message:
                error_msg = _('Error REST XPRESS (código %s): %s', code, message)
                _logger.error(error_msg)
                return {'errors': [error_msg]}

            # Unknown response
            error_msg = _('Respuesta desconocida de REST XPRESS: %s', str(data)[:500])
            _logger.error(error_msg)
            return {'errors': [error_msg]}

        except ValueError:
            error_msg = _('REST XPRESS devolvió una respuesta inválida: %s', response.text[:500])
            _logger.error(error_msg)
            return {'errors': [error_msg]}
        except Exception as e:
            _logger.error('Error parsing cancel response: %s', e, exc_info=True)
            return {'errors': [_('Error al procesar respuesta de REST XPRESS: %s', str(e))]}

    @api.model
    def _rest_xpress_xml_to_json(self, cfdi_xml, company):
        """
        Convert CFDI XML to REST XPRESS JSON format.

        :param cfdi_xml: bytes with CFDI XML
        :param company: res.company record
        :return: dict with JSON structure for REST XPRESS
        """
        try:
            # Log raw XML for debugging - write to file for analysis
            xml_str = cfdi_xml.decode('utf-8') if isinstance(cfdi_xml, bytes) else cfdi_xml
            with open('/tmp/cfdi_nomina_debug.xml', 'w') as f:
                f.write(xml_str)
            _logger.info("Raw CFDI XML written to /tmp/cfdi_nomina_debug.xml")

            # Parse XML
            cfdi_node = etree.fromstring(cfdi_xml)
            namespaces = {
                'cfdi': 'http://www.sat.gob.mx/cfd/4',
                'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
                'nomina12': 'http://www.sat.gob.mx/nomina12',
                'pago20': 'http://www.sat.gob.mx/Pagos20',
            }
            _logger.info("Parsed cfdi_node tag: %s", cfdi_node.tag)

            # Write parsed XML back to file for comparison
            try:
                parsed_xml = etree.tostring(cfdi_node, encoding='unicode', pretty_print=True)
                with open('/tmp/cfdi_nomina_parsed.xml', 'w') as f:
                    f.write(parsed_xml)
                _logger.info("Parsed CFDI XML written to /tmp/cfdi_nomina_parsed.xml")
            except Exception as e:
                _logger.warning("Could not write parsed XML: %s", e)

            # Build Comprobante node - only include fields with values
            comprobante = {
                'Version': cfdi_node.get('Version'),
                'Fecha': cfdi_node.get('Fecha'),
                'SubTotal': cfdi_node.get('SubTotal'),
                'Moneda': cfdi_node.get('Moneda'),
                'Total': cfdi_node.get('Total'),
                'TipoDeComprobante': cfdi_node.get('TipoDeComprobante'),
                'LugarExpedicion': cfdi_node.get('LugarExpedicion'),
            }

            # Add optional fields only if they have values
            optional_fields = {
                'Serie': cfdi_node.get('Serie'),
                'Folio': cfdi_node.get('Folio'),
                'FormaPago': cfdi_node.get('FormaPago'),
                'NoCertificado': cfdi_node.get('NoCertificado'),
                'CondicionesDePago': cfdi_node.get('CondicionesDePago'),
                'Descuento': cfdi_node.get('Descuento'),
                'TipoCambio': cfdi_node.get('TipoCambio'),
                'Exportacion': cfdi_node.get('Exportacion'),
                'MetodoPago': cfdi_node.get('MetodoPago'),
            }
            # Only add non-empty optional fields
            for key, value in optional_fields.items():
                if value:  # Only add if not None and not empty string
                    comprobante[key] = value

            # Add Emisor
            emisor_node = cfdi_node.find('cfdi:Emisor', namespaces)
            if emisor_node is not None:
                comprobante['Emisor'] = {
                    'Rfc': emisor_node.get('Rfc'),
                    'Nombre': emisor_node.get('Nombre'),
                    'RegimenFiscal': emisor_node.get('RegimenFiscal'),
                }

            # Add Receptor
            receptor_node = cfdi_node.find('cfdi:Receptor', namespaces)
            if receptor_node is not None:
                receptor = {
                    'Rfc': receptor_node.get('Rfc'),
                    'Nombre': receptor_node.get('Nombre'),
                    'UsoCFDI': receptor_node.get('UsoCFDI'),
                }
                # Add optional receptor fields
                receptor_optional = {
                    'DomicilioFiscalReceptor': receptor_node.get('DomicilioFiscalReceptor'),
                    'ResidenciaFiscal': receptor_node.get('ResidenciaFiscal'),
                    'NumRegIdTrib': receptor_node.get('NumRegIdTrib'),
                    'RegimenFiscalReceptor': receptor_node.get('RegimenFiscalReceptor'),
                }
                for key, value in receptor_optional.items():
                    if value:
                        receptor[key] = value
                comprobante['Receptor'] = receptor

            # Add Conceptos
            conceptos = []
            conceptos_node = cfdi_node.find('cfdi:Conceptos', namespaces)
            if conceptos_node is not None:
                for concepto_node in conceptos_node.findall('cfdi:Concepto', namespaces):
                    # Required fields
                    concepto = {
                        'ClaveProdServ': concepto_node.get('ClaveProdServ'),
                        'Cantidad': concepto_node.get('Cantidad'),
                        'ClaveUnidad': concepto_node.get('ClaveUnidad'),
                        'Descripcion': concepto_node.get('Descripcion'),
                        'ValorUnitario': concepto_node.get('ValorUnitario'),
                        'Importe': concepto_node.get('Importe'),
                        'ObjetoImp': concepto_node.get('ObjetoImp'),
                    }
                    # Optional fields - only add if they have value
                    concepto_optional = {
                        'NoIdentificacion': concepto_node.get('NoIdentificacion'),
                        'Unidad': concepto_node.get('Unidad'),
                        'Descuento': concepto_node.get('Descuento'),
                    }
                    for key, value in concepto_optional.items():
                        if value:
                            concepto[key] = value

                    # Add taxes if present
                    impuestos_concepto = concepto_node.find('cfdi:Impuestos', namespaces)
                    if impuestos_concepto is not None:
                        concepto['Impuestos'] = {}

                        # Traslados
                        traslados_node = impuestos_concepto.find('cfdi:Traslados', namespaces)
                        if traslados_node is not None:
                            traslados = []
                            for traslado in traslados_node.findall('cfdi:Traslado', namespaces):
                                traslado_dict = {
                                    'Base': traslado.get('Base'),
                                    'Impuesto': traslado.get('Impuesto'),
                                    'TipoFactor': traslado.get('TipoFactor'),
                                }
                                # Optional tax fields
                                if traslado.get('TasaOCuota'):
                                    traslado_dict['TasaOCuota'] = traslado.get('TasaOCuota')
                                if traslado.get('Importe'):
                                    traslado_dict['Importe'] = traslado.get('Importe')
                                traslados.append(traslado_dict)
                            concepto['Impuestos']['Traslados'] = traslados

                        # Retenciones
                        retenciones_node = impuestos_concepto.find('cfdi:Retenciones', namespaces)
                        if retenciones_node is not None:
                            retenciones = []
                            for retencion in retenciones_node.findall('cfdi:Retencion', namespaces):
                                retenciones.append({
                                    'Base': retencion.get('Base'),
                                    'Impuesto': retencion.get('Impuesto'),
                                    'TipoFactor': retencion.get('TipoFactor'),
                                    'TasaOCuota': retencion.get('TasaOCuota'),
                                    'Importe': retencion.get('Importe'),
                                })
                            concepto['Impuestos']['Retenciones'] = retenciones

                    conceptos.append(concepto)

            comprobante['Conceptos'] = conceptos

            # Add Impuestos (global taxes)
            impuestos_node = cfdi_node.find('cfdi:Impuestos', namespaces)
            if impuestos_node is not None:
                impuestos = {}

                # Total amounts
                total_retenciones = impuestos_node.get('TotalImpuestosRetenidos')
                total_traslados = impuestos_node.get('TotalImpuestosTrasladados')
                if total_retenciones:
                    impuestos['TotalImpuestosRetenidos'] = total_retenciones
                if total_traslados:
                    impuestos['TotalImpuestosTrasladados'] = total_traslados

                # Retenciones
                retenciones_node = impuestos_node.find('cfdi:Retenciones', namespaces)
                if retenciones_node is not None:
                    retenciones = []
                    for retencion in retenciones_node.findall('cfdi:Retencion', namespaces):
                        retenciones.append({
                            'Impuesto': retencion.get('Impuesto'),
                            'Importe': retencion.get('Importe'),
                        })
                    impuestos['Retenciones'] = retenciones

                # Traslados
                traslados_node = impuestos_node.find('cfdi:Traslados', namespaces)
                if traslados_node is not None:
                    traslados = []
                    for traslado in traslados_node.findall('cfdi:Traslado', namespaces):
                        traslados.append({
                            'Base': traslado.get('Base', '0.00'),
                            'Impuesto': traslado.get('Impuesto'),
                            'TipoFactor': traslado.get('TipoFactor'),
                            'TasaOCuota': traslado.get('TasaOCuota'),
                            'Importe': traslado.get('Importe', '0.00'),
                        })
                    impuestos['Traslados'] = traslados

                comprobante['Impuestos'] = impuestos

            # Add CfdiRelacionados if present
            relacionados_nodes = cfdi_node.findall('cfdi:CfdiRelacionados', namespaces)
            if relacionados_nodes:
                cfdi_relacionados = []
                for relacionados_node in relacionados_nodes:
                    tipo_relacion = relacionados_node.get('TipoRelacion')
                    uuids = [rel.get('UUID') for rel in relacionados_node.findall('cfdi:CfdiRelacionado', namespaces)]
                    cfdi_relacionados.append({
                        'TipoRelacion': tipo_relacion,
                        'CfdiRelacionado': uuids,
                    })
                comprobante['CfdiRelacionados'] = cfdi_relacionados

            # Add Complemento if present (for Pagos, Nomina, Carta Porte, etc.)
            complemento_node = cfdi_node.find('cfdi:Complemento', namespaces)
            if complemento_node is not None:
                _logger.info("Found Complemento node tag: %s", complemento_node.tag)
                _logger.info("Complemento node has %d direct children", len(list(complemento_node)))
                for i, c in enumerate(complemento_node):
                    _logger.info("  Child %d: tag=%s, localname=%s", i, c.tag, etree.QName(c).localname)
                comprobante['Complemento'] = self._rest_xpress_parse_complemento(complemento_node)

            # Build CamposPDF (additional PDF fields)
            tipo_comprobante_map = {
                'I': 'FACTURA',
                'E': 'NOTA DE CREDITO',
                'T': 'TRASLADO',
                'P': 'PAGO',
                'N': 'NOMINA',
            }
            campos_pdf = {
                'tipoComprobante': tipo_comprobante_map.get(cfdi_node.get('TipoDeComprobante'), 'FACTURA'),
                'Comentarios': '',
            }

            # Add logo if available
            logo_b64 = ''
            if company.logo:
                logo_b64 = company.logo.decode('utf-8') if isinstance(company.logo, bytes) else company.logo

            # Build final JSON structure
            return {
                'Comprobante': comprobante,
                'CamposPDF': campos_pdf,
                'logo': logo_b64,
            }

        except Exception as e:
            _logger.error('Error converting CFDI XML to JSON: %s', str(e), exc_info=True)
            return None

    @api.model
    def _rest_xpress_parse_complemento(self, complemento_node):
        """
        Parse CFDI Complemento node to dict (for Pagos, Nomina, Carta Porte, etc.).

        This parser converts any XML complemento to dict recursively.

        :param complemento_node: lxml.etree.Element of the Complemento node
        :return: list of dicts with complemento data
        """
        complementos = []

        # Log complemento structure for debugging
        _logger.info("Parsing Complemento node tag: %s", complemento_node.tag)
        _logger.info("Parsing Complemento node with %d children", len(list(complemento_node)))

        # Log the actual XML of the complemento node for debugging
        try:
            complemento_xml = etree.tostring(complemento_node, encoding='unicode', pretty_print=True)
            _logger.info("Complemento XML (first 1000 chars):\n%s", complemento_xml[:1000])
        except Exception as e:
            _logger.warning("Could not serialize complemento node: %s", e)

        for child in complemento_node:
            # Get local name without namespace
            tag = etree.QName(child).localname
            ns = etree.QName(child).namespace
            _logger.info("Found complemento child: localname=%s, namespace=%s, full_tag=%s", tag, ns, child.tag)

            # Skip if this is somehow another Complemento element (shouldn't happen)
            if tag == 'Complemento' and ns == 'http://www.sat.gob.mx/cfd/4':
                _logger.warning("Skipping nested cfdi:Complemento element - this indicates an XML parsing issue")
                continue

            # Parse child recursively
            complemento_dict = {tag: self._rest_xpress_xml_node_to_dict(child)}
            complementos.append(complemento_dict)

        return complementos

    # Elements that should always be arrays in CFDI/Nomina JSON structure
    # even when there's only one element
    CFDI_ARRAY_ELEMENTS = {
        # Nómina complement
        'Percepcion',
        'Deduccion',
        'OtroPago',
        'Incapacidad',
        'HorasExtra',
        'JubilacionPensionRetiro',
        'SeparacionIndemnizacion',
        # Pagos complement
        'Pago',
        'DoctoRelacionado',
        # General CFDI
        'Concepto',
        'Traslado',
        'Retencion',
        'CfdiRelacionado',
    }

    @api.model
    def _rest_xpress_xml_node_to_dict(self, node, depth=0, max_depth=50):
        """
        Recursively convert XML node to dictionary.

        :param node: lxml.etree.Element
        :param depth: current recursion depth
        :param max_depth: maximum recursion depth to prevent infinite loops
        :return: dict with node data
        """
        result = {}

        # Prevent infinite recursion
        if depth > max_depth:
            _logger.warning("Maximum recursion depth reached parsing XML node: %s", etree.QName(node).localname)
            return result

        # Add attributes
        for key, value in node.attrib.items():
            # Clean attribute key (remove namespace if present)
            clean_key = key.split('}')[-1] if '}' in key else key
            result[clean_key] = value

        # Process children
        for child in node:
            tag = etree.QName(child).localname
            child_dict = self._rest_xpress_xml_node_to_dict(child, depth + 1, max_depth)

            # If tag already exists, convert to list
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_dict)
            else:
                # Force array for elements that should always be arrays
                if tag in self.CFDI_ARRAY_ELEMENTS:
                    result[tag] = [child_dict]
                else:
                    result[tag] = child_dict

        return result

    # ===========================
    # REST XPRESS Additional Services
    # ===========================

    @api.model
    def _rest_xpress_get_credits(self, credentials):
        """
        Query available credits (timbres) from REST XPRESS.

        Endpoint: consultarCreditosDisponibles
        Does NOT consume credits.

        :param credentials: dict with api_key, credits_url
        :return: dict with credits count or errors
        """
        try:
            payload = {
                'apikey': credentials['api_key'],
            }

            _logger.info('REST XPRESS: Querying available credits')
            response = requests.post(
                credentials['credits_url'],
                data=payload,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            _logger.info('REST XPRESS credits response: %s', data)

            code = str(data.get('code', ''))
            if code == '200':
                credits = data.get('data', 0)
                try:
                    credits = int(credits)
                except (ValueError, TypeError):
                    credits = 0
                return {
                    'success': True,
                    'credits': credits,
                    'message': data.get('message', ''),
                }

            return {
                'success': False,
                'credits': 0,
                'errors': [_('REST XPRESS error (code %s): %s', code, data.get('message', ''))],
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'credits': 0, 'errors': [_('REST XPRESS timeout')]}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'credits': 0, 'errors': [_('REST XPRESS connection error: %s', str(e))]}
        except Exception as e:
            _logger.error('REST XPRESS credits error: %s', str(e), exc_info=True)
            return {'success': False, 'credits': 0, 'errors': [_('REST XPRESS error: %s', str(e))]}

    @api.model
    def _rest_xpress_check_sat_status(self, credentials, uuid, rfc_emisor, rfc_receptor, total):
        """
        Query CFDI status directly from SAT via REST XPRESS.

        Endpoint: consultarEstadoSAT
        Does NOT consume credits.

        :param credentials: dict with api_key, status_url
        :param uuid: str with CFDI UUID
        :param rfc_emisor: str with issuer RFC
        :param rfc_receptor: str with receiver RFC
        :param total: str/float with CFDI total amount
        :return: dict with SAT status information
        """
        try:
            payload = {
                'apikey': credentials['api_key'],
                'uuid': uuid,
                'rfcEmisor': rfc_emisor,
                'rfcReceptor': rfc_receptor,
                'total': str(total),
            }

            _logger.info('REST XPRESS: Checking SAT status for UUID %s', uuid)
            response = requests.post(
                credentials['status_url'],
                data=payload,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            _logger.info('REST XPRESS SAT status response: %s', data)

            # Parse SAT response fields
            codigo_estatus = data.get('CodigoEstatus', '')
            es_cancelable = data.get('EsCancelable', '')
            estado = data.get('Estado', '')
            estatus_cancelacion = data.get('EstatusCancelacion', '')

            # Check if query was successful
            if codigo_estatus.startswith('S'):
                return {
                    'success': True,
                    'codigo_estatus': codigo_estatus,
                    'es_cancelable': es_cancelable,
                    'estado': estado,
                    'estatus_cancelacion': estatus_cancelacion,
                }

            # Error responses
            if codigo_estatus == 'N 601':
                return {
                    'success': False,
                    'estado': 'No Encontrado',
                    'errors': [_('La expresión impresa proporcionada no es válida')],
                }

            if codigo_estatus == 'N 602':
                return {
                    'success': False,
                    'estado': 'No Encontrado',
                    'errors': [_('Comprobante no encontrado en el SAT')],
                }

            return {
                'success': False,
                'estado': data.get('Estado', 'Desconocido'),
                'errors': [_('REST XPRESS: %s', codigo_estatus or 'Error desconocido')],
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'estado': 'Error', 'errors': [_('REST XPRESS timeout')]}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'estado': 'Error', 'errors': [_('REST XPRESS connection error: %s', str(e))]}
        except Exception as e:
            _logger.error('REST XPRESS SAT status error: %s', str(e), exc_info=True)
            return {'success': False, 'estado': 'Error', 'errors': [_('REST XPRESS error: %s', str(e))]}
