# -*- coding: utf-8 -*-

from unittest.mock import Mock, patch
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPACRestXpress(TransactionCase):
    """
    Test cases for REST XPRESS PAC integration.

    These tests verify:
    - Configuration and credentials
    - XML to JSON conversion
    - Sign response parsing
    - Cancel response parsing
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get test company
        cls.company = cls.env.company

        # Configure company for REST XPRESS
        cls.company.write({
            'l10n_mx_edi_pac': 'rest_xpress',
            'l10n_mx_edi_pac_password': 'test_api_key_12345',
            'l10n_mx_edi_pac_test_env': True,
        })

        # Get EDI format
        cls.edi_format = cls.env['account.edi.format'].search([
            ('code', '=', 'cfdi_3_3')
        ], limit=1)

    def test_01_rest_xpress_credentials(self):
        """Test that REST XPRESS credentials are correctly configured."""
        credentials = self.company._l10n_mx_edi_get_pac_credentials()

        self.assertEqual(credentials['api_key'], 'test_api_key_12345')
        self.assertTrue(credentials['test_mode'])
        self.assertIn('timbrador.restxpress.com', credentials['sign_url'])
        self.assertIn('timbrador.restxpress.com', credentials['cancel_url'])

    def test_02_xml_to_json_conversion(self):
        """Test CFDI XML to REST XPRESS JSON conversion."""
        # Sample CFDI XML
        cfdi_xml = b'''<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
                   Version="4.0" Serie="A" Folio="123"
                   Fecha="2024-01-06T10:00:00"
                   TipoDeComprobante="I"
                   SubTotal="100.00" Total="116.00"
                   Moneda="MXN" LugarExpedicion="06000"
                   Exportacion="01" MetodoPago="PUE" FormaPago="03">
    <cfdi:Emisor Rfc="EKU9003173C9" Nombre="Test Company" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="XAXX010101000" Nombre="Test Customer"
                   DomicilioFiscalReceptor="06000"
                   RegimenFiscalReceptor="616" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1.0"
                       ClaveUnidad="H87" Descripcion="Test Product"
                       ValorUnitario="100.00" Importe="100.00"
                       ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="100.00" Impuesto="002"
                                   TipoFactor="Tasa" TasaOCuota="0.160000"
                                   Importe="16.00"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>
    </cfdi:Conceptos>
    <cfdi:Impuestos TotalImpuestosTrasladados="16.00">
        <cfdi:Traslados>
            <cfdi:Traslado Base="100.00" Impuesto="002"
                           TipoFactor="Tasa" TasaOCuota="0.160000"
                           Importe="16.00"/>
        </cfdi:Traslados>
    </cfdi:Impuestos>
</cfdi:Comprobante>'''

        # Create mock move
        move = Mock()
        move.narration = 'Test narration'
        move.partner_id.street = 'Test Street'
        move.partner_id.zip = '06000'
        move.partner_id.city = 'Test City'
        move.partner_id.state_id.name = 'Test State'

        # Convert XML to JSON
        json_data = self.edi_format._l10n_mx_edi_rest_xpress_xml_to_json(
            cfdi_xml, self.company, move
        )

        # Verify JSON structure
        self.assertIsNotNone(json_data)
        self.assertIn('Comprobante', json_data)
        self.assertIn('CamposPDF', json_data)
        self.assertIn('logo', json_data)

        # Verify Comprobante data
        comprobante = json_data['Comprobante']
        self.assertEqual(comprobante['Version'], '4.0')
        self.assertEqual(comprobante['Serie'], 'A')
        self.assertEqual(comprobante['Folio'], '123')
        self.assertEqual(comprobante['TipoDeComprobante'], 'I')
        self.assertEqual(comprobante['Total'], '116.00')

        # Verify Emisor
        self.assertEqual(comprobante['Emisor']['Rfc'], 'EKU9003173C9')

        # Verify Receptor
        self.assertEqual(comprobante['Receptor']['Rfc'], 'XAXX010101000')

        # Verify Conceptos
        self.assertEqual(len(comprobante['Conceptos']), 1)
        self.assertEqual(comprobante['Conceptos'][0]['Descripcion'], 'Test Product')

    def test_03_parse_sign_response_success(self):
        """Test parsing successful sign response from REST XPRESS."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'cfdiTimbrado': 'base64_encoded_cfdi_here',
        }

        result = self.edi_format._l10n_mx_edi_rest_xpress_parse_sign_response(mock_response)

        self.assertIn('cfdi_signed', result)
        self.assertNotIn('errors', result)

    def test_04_parse_sign_response_error(self):
        """Test parsing error sign response from REST XPRESS."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'error',
            'mensaje': 'Invalid certificate',
        }

        result = self.edi_format._l10n_mx_edi_rest_xpress_parse_sign_response(mock_response)

        self.assertIn('errors', result)
        self.assertIn('Invalid certificate', str(result['errors']))

    def test_05_parse_cancel_response_success(self):
        """Test parsing successful cancel response from REST XPRESS."""
        # Mock successful cancellation
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'success',
            'estatusCancelacion': 'Cancelado',
        }

        result = self.edi_format._l10n_mx_edi_rest_xpress_parse_cancel_response(mock_response)

        self.assertTrue(result.get('success'))
        self.assertNotIn('errors', result)

    def test_06_parse_cancel_response_pending(self):
        """Test parsing pending cancel response from REST XPRESS."""
        # Mock pending cancellation
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'En proceso',
            'estatusCancelacion': 'En proceso',
        }

        result = self.edi_format._l10n_mx_edi_rest_xpress_parse_cancel_response(mock_response)

        self.assertIn('errors', result)
        self.assertIn('Awaiting SAT confirmation', str(result['errors']))
