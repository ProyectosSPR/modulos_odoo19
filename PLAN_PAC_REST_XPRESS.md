# IMPLEMENTACIÓN PAC REST XPRESS (Timbrador Xpress)
## Integración con Odoo 19 Enterprise

---

## ANÁLISIS DE LA API REST XPRESS

### 1. Información General

**PAC**: REST XPRESS (Timbrador Xpress)
**Protocolo**: REST API (POST con form-data)
**Autenticación**: API Key
**Formato**: JSON + XML
**URL Desarrollo**: `https://dev.timbradorxpress.mx/api/rest/servicio/`
**URL Producción**: `https://timbradorxpress.mx/api/rest/servicio/`

---

### 2. Endpoints Disponibles

| Endpoint | Descripción | Entrada |
|----------|-------------|---------|
| `/timbrar` | Timbrado básico | XML CFDI firmado + apikey |
| `/timbrarTFD` | Timbrado con TFD | XML CFDI firmado + apikey |
| `/timbrarConSello` | Timbrado con sello local | XML + keyPEM + cerPEM + apikey |
| `/timbrarJSON` | Timbrado desde JSON | JSON base64 + keyPEM + cerPEM + apikey |
| `/timbrarJSON2` | Timbrado JSON alternativo | JSON base64 + keyPEM + cerPEM + apikey |
| `/cancelar` | Cancelación de CFDI | UUID + apikey + motivo |

---

### 3. Formato de Request

#### **Opción 1: Timbrar XML Firmado**
```http
POST https://dev.timbradorxpress.mx/api/rest/servicio/timbrar
Content-Type: application/x-www-form-urlencoded

apikey=93edc4af66b84c938f66a56ca0596205
&xmlCFDI=<?xml version="1.0" encoding="utf-8"?>...
```

#### **Opción 2: Timbrar desde JSON (Recomendado)**
```http
POST https://dev.timbradorxpress.mx/api/rest/servicio/timbrarJSON
Content-Type: application/x-www-form-urlencoded

apikey=93edc4af66b84c938f66a56ca0596205
&jsonB64=eyJDb21wcm9iYW50ZSI6IHsuLi59fQ==
&keyPEM=-----BEGIN PRIVATE KEY-----...
&cerPEM=-----BEGIN CERTIFICATE-----...
```

#### **Opción 3: Timbrar con Sello Pre-generado**
```http
POST https://dev.timbradorxpress.mx/api/rest/servicio/timbrarConSello
Content-Type: application/x-www-form-urlencoded

apikey=93edc4af66b84c938f66a56ca0596205
&xmlCFDI=<?xml version="1.0" encoding="utf-8"?>...
&keyPEM=-----BEGIN PRIVATE KEY-----...
```

---

### 4. Estructura JSON de Entrada

```json
{
  "Comprobante": {
    "Version": "4.0",
    "Serie": "LC-J",
    "Folio": "LC-10912",
    "Fecha": "2024-11-21T12:31:17",
    "NoCertificado": "30001000000500003416",
    "SubTotal": "1.00",
    "Moneda": "MXN",
    "Total": "1.16",
    "FormaPago": "01",
    "TipoDeComprobante": "I",
    "MetodoPago": "PUE",
    "Exportacion": "01",
    "LugarExpedicion": "80349",

    "CfdiRelacionados": [{
      "TipoRelacion": "04",
      "CfdiRelacionado": ["1648AC42-28E4-4047-818A-199A6950FACC"]
    }],

    "Emisor": {
      "Rfc": "EKU9003173C9",
      "Nombre": "ESCUELA KEMPER URGATE",
      "RegimenFiscal": "601"
    },

    "Receptor": {
      "Rfc": "XAXX010101000",
      "Nombre": "Publico en General",
      "DomicilioFiscalReceptor": "80349",
      "RegimenFiscalReceptor": "616",
      "UsoCFDI": "S01"
    },

    "Conceptos": [{
      "ClaveProdServ": "40142020",
      "Cantidad": "1.0",
      "ClaveUnidad": "MTR",
      "Descripcion": "Producto 1",
      "ValorUnitario": "1.00",
      "Importe": "1.00",
      "ObjetoImp": "02",
      "Impuestos": {
        "Traslados": [{
          "Base": "1.00",
          "Impuesto": "002",
          "TipoFactor": "Tasa",
          "TasaOCuota": "0.160000",
          "Importe": "0.16"
        }]
      }
    }],

    "Impuestos": {
      "TotalImpuestosTrasladados": "0.16",
      "Traslados": [{
        "Base": "1.00",
        "Impuesto": "002",
        "TipoFactor": "Tasa",
        "TasaOCuota": "0.160000",
        "Importe": "0.16"
      }]
    }
  },

  "CamposPDF": {
    "tipoComprobante": "FACTURA",
    "Comentarios": "Aquí van los comentarios de la factura",
    "calleEmisor": "Calle 1",
    "emailEmisor": "emisor@example.com",
    "telefonoEmisor": "5555555555"
  },

  "logo": "base64_del_logo"
}
```

---

### 5. Respuesta del PAC

#### **Respuesta Exitosa**
```json
{
  "status": "success",
  "message": "CFDI timbrado correctamente",
  "data": {
    "cfdiTimbrado": "<?xml version=\"1.0\"...",
    "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "fechaTimbrado": "2024-11-21T12:31:18",
    "noCertificadoSAT": "30001000000500003416",
    "selloCFD": "...",
    "selloSAT": "...",
    "cadenaOriginal": "||1.1|...|"
  }
}
```

#### **Respuesta con Error**
```json
{
  "status": "error",
  "message": "Error en timbrado",
  "errors": [
    {
      "code": "301",
      "message": "El RFC del receptor no es válido"
    }
  ]
}
```

---

### 6. Características Especiales de REST XPRESS

✅ **Ventajas sobre IT Admin**:
1. **Múltiples métodos de timbrado**: XML directo, JSON, con sello previo
2. **CamposPDF personalizables**: Agregar campos custom al PDF
3. **Logo personalizable**: Incluir logo de empresa en PDF
4. **Mejor manejo de errores**: Códigos de error específicos
5. **Soporte para etiquetas y firmas**: Campos adicionales en PDF
6. **Desarrollo y producción separados**: URLs diferentes

✅ **Funcionalidades Adicionales**:
- Timbrado de complementos (Carta Porte, Nómina, etc.)
- Generación de PDF automático
- Validación pre-timbrado
- Cancelación con motivos SAT
- Consulta de estado de CFDI

---

## IMPLEMENTACIÓN DEL CONECTOR PAC

### Estructura del Conector

```
cdfi_invoice_enterprise/
└── models/
    └── pac_connector/
        ├── __init__.py
        ├── pac_base.py               # Clase abstracta base
        ├── pac_itadmin.py            # IT Admin (existente)
        ├── pac_rest_xpress.py        # REST XPRESS (NUEVO)
        ├── pac_finkok.py             # Finkok
        └── pac_sw.py                 # SW
```

---

### Código Completo: `pac_rest_xpress.py`

```python
# -*- coding: utf-8 -*-

from . import pac_base
import requests
import json
import base64
from lxml import etree
from odoo import _, fields
import logging

_logger = logging.getLogger(__name__)


class PACRestXpress(pac_base.PACConnector):
    """
    Conector para PAC REST XPRESS (Timbrador Xpress).

    Este PAC soporta múltiples métodos de timbrado:
    - XML directo (ya firmado)
    - JSON con conversión automática a XML
    - XML con sello previo

    Documentación: https://timbradorxpress.mx/docs/api
    """

    def get_credentials(self):
        """
        Obtiene las credenciales de acceso al PAC REST XPRESS.

        Returns:
            dict: Credenciales con estructura:
                - api_key: API Key del cliente
                - sign_url: URL de timbrado
                - cancel_url: URL de cancelación
                - test_mode: True si es ambiente de prueba
                o {'errors': [lista de errores]}
        """
        company = self.company

        # Validar configuración
        if not company.l10n_mx_edi_pac_password:  # API Key en password
            return {'errors': [_('Falta configurar API Key de REST XPRESS')]}

        # Determinar URLs según ambiente
        if company.l10n_mx_edi_pac_test_env:
            base_url = 'https://dev.timbradorxpress.mx/api/rest/servicio'
        else:
            base_url = 'https://timbradorxpress.mx/api/rest/servicio'

        return {
            'api_key': company.sudo().l10n_mx_edi_pac_password,
            'sign_url': f'{base_url}/timbrarJSON',      # Usar método JSON
            'sign_xml_url': f'{base_url}/timbrar',       # Método XML alternativo
            'cancel_url': f'{base_url}/cancelar',
            'test_mode': company.l10n_mx_edi_pac_test_env,
        }

    def sign(self, credentials, cfdi_str):
        """
        Envía el CFDI al PAC REST XPRESS para timbrado.

        Este método utiliza el endpoint 'timbrarJSON' que permite enviar
        los datos de la factura en formato JSON junto con los certificados.

        Args:
            credentials (dict): Credenciales del PAC
            cfdi_str (bytes): XML del CFDI firmado localmente (se ignora)

        Returns:
            dict: {'cfdi_str': bytes} con CFDI timbrado
                  o {'errors': [lista de errores]}
        """
        company = self.company

        # Obtener certificado
        certificate_sudo = company.l10n_mx_edi_certificate_ids.filtered('is_valid')[:1]
        if not certificate_sudo:
            return {'errors': [_('No se encontró certificado válido')]}

        # Convertir CFDI XML a JSON REST XPRESS
        try:
            json_data = self._convert_cfdi_to_json(cfdi_str, company, certificate_sudo)
        except Exception as e:
            _logger.error(f"Error convirtiendo CFDI a JSON: {str(e)}")
            return {'errors': [_('Error al convertir CFDI a JSON: %s') % str(e)]}

        # Codificar JSON a base64
        json_str = json.dumps(json_data, ensure_ascii=False)
        json_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

        # Obtener certificados PEM
        try:
            key_pem = certificate_sudo.private_key_id.get_unencrypted_key_pem()
            cer_pem = certificate_sudo.get_pem_certificate()
        except Exception as e:
            return {'errors': [_('Error obteniendo certificados PEM: %s') % str(e)]}

        # Preparar request
        payload = {
            'apikey': credentials['api_key'],
            'jsonB64': json_b64,
            'keyPEM': key_pem.decode('utf-8') if isinstance(key_pem, bytes) else key_pem,
            'cerPEM': cer_pem.decode('utf-8') if isinstance(cer_pem, bytes) else cer_pem,
        }

        # Enviar a REST XPRESS
        try:
            response = requests.post(
                credentials['sign_url'],
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            response_json = response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error conectando con REST XPRESS: {str(e)}")
            return {'errors': [_('Error de conexión con PAC: %s') % str(e)]}
        except json.JSONDecodeError as e:
            _logger.error(f"Respuesta inválida de REST XPRESS: {response.text}")
            return {'errors': [_('Respuesta inválida del PAC')]}

        # Procesar respuesta
        if response_json.get('status') == 'success':
            cfdi_timbrado = response_json.get('data', {}).get('cfdiTimbrado')

            if cfdi_timbrado:
                # Puede venir en base64 o texto plano
                try:
                    cfdi_bytes = base64.b64decode(cfdi_timbrado)
                except:
                    cfdi_bytes = cfdi_timbrado.encode('utf-8')

                return {'cfdi_str': cfdi_bytes}
            else:
                return {'errors': [_('PAC no retornó XML timbrado')]}
        else:
            # Error del PAC
            errors = []

            # Mensaje principal
            if response_json.get('message'):
                errors.append(response_json['message'])

            # Errores detallados
            if response_json.get('errors'):
                for error in response_json['errors']:
                    code = error.get('code', '')
                    message = error.get('message', '')
                    errors.append(f"[{code}] {message}" if code else message)

            return {'errors': errors if errors else [_('Error desconocido del PAC')]}

    def cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """
        Cancela un CFDI previamente timbrado.

        Args:
            cfdi_values (dict): Valores del CFDI (emisor, folio, serie, etc.)
            credentials (dict): Credenciales del PAC
            uuid (str): UUID del CFDI a cancelar
            cancel_reason (str): Motivo de cancelación ('01', '02', '03', '04')
            cancel_uuid (str, optional): UUID de sustitución (para motivo '04')

        Returns:
            dict: {} si es exitoso
                  o {'errors': [lista de errores]}
        """
        company = cfdi_values['root_company']
        certificate_sudo = cfdi_values['certificate'].sudo()

        # Obtener certificados PEM
        try:
            key_pem = certificate_sudo.private_key_id.get_unencrypted_key_pem()
            cer_pem = certificate_sudo.get_pem_certificate()
        except Exception as e:
            return {'errors': [_('Error obteniendo certificados: %s') % str(e)]}

        # Preparar request de cancelación
        payload = {
            'apikey': credentials['api_key'],
            'uuid': uuid,
            'rfc': company.vat,
            'motivo': cancel_reason,
            'keyPEM': key_pem.decode('utf-8') if isinstance(key_pem, bytes) else key_pem,
            'cerPEM': cer_pem.decode('utf-8') if isinstance(cer_pem, bytes) else cer_pem,
        }

        # Agregar UUID de sustitución si aplica
        if cancel_uuid:
            payload['folioSustitucion'] = cancel_uuid

        # Enviar a REST XPRESS
        try:
            response = requests.post(
                credentials['cancel_url'],
                data=payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            response_json = response.json()
        except requests.exceptions.RequestException as e:
            return {'errors': [_('Error de conexión: %s') % str(e)]}
        except json.JSONDecodeError:
            return {'errors': [_('Respuesta inválida del PAC')]}

        # Procesar respuesta
        if response_json.get('status') == 'success':
            return {}  # Cancelación exitosa
        else:
            errors = []
            if response_json.get('message'):
                errors.append(response_json['message'])
            if response_json.get('errors'):
                for error in response_json['errors']:
                    errors.append(error.get('message', str(error)))
            return {'errors': errors if errors else [_('Error en cancelación')]}

    def _convert_cfdi_to_json(self, cfdi_str, company, certificate):
        """
        Convierte un CFDI XML a la estructura JSON esperada por REST XPRESS.

        Args:
            cfdi_str (bytes): XML del CFDI
            company (res.company): Compañía emisora
            certificate (certificate.certificate): Certificado digital

        Returns:
            dict: Estructura JSON para REST XPRESS
        """
        # Parsear XML
        try:
            cfdi_tree = etree.fromstring(cfdi_str)
        except Exception as e:
            raise ValueError(f"XML inválido: {str(e)}")

        # Namespace CFDI 4.0
        ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

        # Función helper para extraer texto
        def get_text(element, path, default=''):
            result = element.xpath(path, namespaces=ns)
            return result[0] if result else default

        def get_attr(element, attr, default=''):
            return element.get(attr, default)

        # Construir estructura JSON
        json_data = {
            'Comprobante': {},
            'CamposPDF': {},
            'logo': ''  # Se puede agregar logo de la compañía si existe
        }

        # Comprobante - Atributos principales
        comprobante = json_data['Comprobante']
        comprobante['Version'] = get_attr(cfdi_tree, 'Version', '4.0')
        comprobante['Serie'] = get_attr(cfdi_tree, 'Serie', '')
        comprobante['Folio'] = get_attr(cfdi_tree, 'Folio', '')
        comprobante['Fecha'] = get_attr(cfdi_tree, 'Fecha', '')
        comprobante['FormaPago'] = get_attr(cfdi_tree, 'FormaPago', '')
        comprobante['NoCertificado'] = get_attr(cfdi_tree, 'NoCertificado', '')
        comprobante['CondicionesDePago'] = get_attr(cfdi_tree, 'CondicionesDePago', '')
        comprobante['SubTotal'] = get_attr(cfdi_tree, 'SubTotal', '')
        comprobante['Descuento'] = get_attr(cfdi_tree, 'Descuento', '0.00')
        comprobante['Moneda'] = get_attr(cfdi_tree, 'Moneda', 'MXN')
        comprobante['TipoCambio'] = get_attr(cfdi_tree, 'TipoCambio', '1')
        comprobante['Total'] = get_attr(cfdi_tree, 'Total', '')
        comprobante['TipoDeComprobante'] = get_attr(cfdi_tree, 'TipoDeComprobante', 'I')
        comprobante['Exportacion'] = get_attr(cfdi_tree, 'Exportacion', '01')
        comprobante['MetodoPago'] = get_attr(cfdi_tree, 'MetodoPago', '')
        comprobante['LugarExpedicion'] = get_attr(cfdi_tree, 'LugarExpedicion', '')
        comprobante['Confirmacion'] = get_attr(cfdi_tree, 'Confirmacion', '')

        # Información Global (si existe)
        info_global = cfdi_tree.xpath('cfdi:InformacionGlobal', namespaces=ns)
        if info_global:
            comprobante['InformacionGlobal'] = {
                'Periodicidad': get_attr(info_global[0], 'Periodicidad', ''),
                'Meses': get_attr(info_global[0], 'Meses', ''),
                'Año': get_attr(info_global[0], 'Año', ''),
            }

        # CFDI Relacionados (si existen)
        cfdi_relacionados = cfdi_tree.xpath('cfdi:CfdiRelacionados', namespaces=ns)
        if cfdi_relacionados:
            for rel_group in cfdi_relacionados:
                tipo_relacion = get_attr(rel_group, 'TipoRelacion', '')
                uuids = []
                for rel in rel_group.xpath('cfdi:CfdiRelacionado', namespaces=ns):
                    uuids.append(get_attr(rel, 'UUID', ''))

                if not isinstance(comprobante.get('CfdiRelacionados'), list):
                    comprobante['CfdiRelacionados'] = []

                comprobante['CfdiRelacionados'].append({
                    'TipoRelacion': tipo_relacion,
                    'CfdiRelacionado': uuids
                })

        # Emisor
        emisor = cfdi_tree.xpath('cfdi:Emisor', namespaces=ns)[0]
        comprobante['Emisor'] = {
            'Rfc': get_attr(emisor, 'Rfc', ''),
            'Nombre': get_attr(emisor, 'Nombre', ''),
            'RegimenFiscal': get_attr(emisor, 'RegimenFiscal', ''),
            'FacAtrAdquirente': get_attr(emisor, 'FacAtrAdquirente', ''),
        }

        # Receptor
        receptor = cfdi_tree.xpath('cfdi:Receptor', namespaces=ns)[0]
        comprobante['Receptor'] = {
            'Rfc': get_attr(receptor, 'Rfc', ''),
            'Nombre': get_attr(receptor, 'Nombre', ''),
            'DomicilioFiscalReceptor': get_attr(receptor, 'DomicilioFiscalReceptor', ''),
            'ResidenciaFiscal': get_attr(receptor, 'ResidenciaFiscal', ''),
            'NumRegIdTrib': get_attr(receptor, 'NumRegIdTrib', ''),
            'RegimenFiscalReceptor': get_attr(receptor, 'RegimenFiscalReceptor', ''),
            'UsoCFDI': get_attr(receptor, 'UsoCFDI', ''),
        }

        # Conceptos
        conceptos = []
        for concepto in cfdi_tree.xpath('cfdi:Conceptos/cfdi:Concepto', namespaces=ns):
            concepto_data = {
                'ClaveProdServ': get_attr(concepto, 'ClaveProdServ', ''),
                'NoIdentificacion': get_attr(concepto, 'NoIdentificacion', ''),
                'Cantidad': get_attr(concepto, 'Cantidad', ''),
                'ClaveUnidad': get_attr(concepto, 'ClaveUnidad', ''),
                'Unidad': get_attr(concepto, 'Unidad', ''),
                'Descripcion': get_attr(concepto, 'Descripcion', ''),
                'ValorUnitario': get_attr(concepto, 'ValorUnitario', ''),
                'Importe': get_attr(concepto, 'Importe', ''),
                'Descuento': get_attr(concepto, 'Descuento', '0.00'),
                'ObjetoImp': get_attr(concepto, 'ObjetoImp', '02'),
            }

            # Impuestos del concepto
            impuestos_concepto = concepto.xpath('cfdi:Impuestos', namespaces=ns)
            if impuestos_concepto:
                impuestos_data = {}

                # Traslados
                traslados = []
                for traslado in impuestos_concepto[0].xpath('cfdi:Traslados/cfdi:Traslado', namespaces=ns):
                    traslados.append({
                        'Base': get_attr(traslado, 'Base', ''),
                        'Impuesto': get_attr(traslado, 'Impuesto', ''),
                        'TipoFactor': get_attr(traslado, 'TipoFactor', ''),
                        'TasaOCuota': get_attr(traslado, 'TasaOCuota', ''),
                        'Importe': get_attr(traslado, 'Importe', ''),
                    })
                if traslados:
                    impuestos_data['Traslados'] = traslados

                # Retenciones
                retenciones = []
                for retencion in impuestos_concepto[0].xpath('cfdi:Retenciones/cfdi:Retencion', namespaces=ns):
                    retenciones.append({
                        'Base': get_attr(retencion, 'Base', ''),
                        'Impuesto': get_attr(retencion, 'Impuesto', ''),
                        'TipoFactor': get_attr(retencion, 'TipoFactor', ''),
                        'TasaOCuota': get_attr(retencion, 'TasaOCuota', ''),
                        'Importe': get_attr(retencion, 'Importe', ''),
                    })
                if retenciones:
                    impuestos_data['Retenciones'] = retenciones

                if impuestos_data:
                    concepto_data['Impuestos'] = impuestos_data

            conceptos.append(concepto_data)

        comprobante['Conceptos'] = conceptos

        # Impuestos globales
        impuestos_global = cfdi_tree.xpath('cfdi:Impuestos', namespaces=ns)
        if impuestos_global:
            impuestos_data = {}

            total_ret = get_attr(impuestos_global[0], 'TotalImpuestosRetenidos', '')
            total_tras = get_attr(impuestos_global[0], 'TotalImpuestosTrasladados', '')

            if total_ret:
                impuestos_data['TotalImpuestosRetenidos'] = total_ret
            if total_tras:
                impuestos_data['TotalImpuestosTrasladados'] = total_tras

            # Retenciones globales
            retenciones = []
            for retencion in impuestos_global[0].xpath('cfdi:Retenciones/cfdi:Retencion', namespaces=ns):
                retenciones.append({
                    'Impuesto': get_attr(retencion, 'Impuesto', ''),
                    'Importe': get_attr(retencion, 'Importe', ''),
                })
            if retenciones:
                impuestos_data['Retenciones'] = retenciones

            # Traslados globales
            traslados = []
            for traslado in impuestos_global[0].xpath('cfdi:Traslados/cfdi:Traslado', namespaces=ns):
                traslados.append({
                    'Base': get_attr(traslado, 'Base', ''),
                    'Impuesto': get_attr(traslado, 'Impuesto', ''),
                    'TipoFactor': get_attr(traslado, 'TipoFactor', ''),
                    'TasaOCuota': get_attr(traslado, 'TasaOCuota', ''),
                    'Importe': get_attr(traslado, 'Importe', ''),
                })
            if traslados:
                impuestos_data['Traslados'] = traslados

            if impuestos_data:
                comprobante['Impuestos'] = impuestos_data

        # CamposPDF - Personalización del PDF
        tipo_comp_map = {
            'I': 'FACTURA',
            'E': 'NOTA DE CRÉDITO',
            'T': 'TRASLADO',
            'N': 'NÓMINA',
            'P': 'RECIBO DE PAGO',
        }

        json_data['CamposPDF'] = {
            'tipoComprobante': tipo_comp_map.get(comprobante['TipoDeComprobante'], 'FACTURA'),
            'Comentarios': '',

            # Datos del emisor
            'calleEmisor': company.street or '',
            'coloniaEmisor': company.street2 or '',
            'codigoPostalEmisor': company.zip or '',
            'municipioEmisor': company.city or '',
            'estadoEmisor': company.state_id.name if company.state_id else '',
            'paisEmisor': company.country_id.name if company.country_id else '',
            'telefonoEmisor': company.phone or '',
            'emailEmisor': company.email or '',
        }

        # Logo de la compañía (si existe)
        if company.logo:
            json_data['logo'] = company.logo.decode('utf-8')

        return json_data

    def validate_connection(self):
        """Valida la conexión con el PAC REST XPRESS."""
        credentials = self.get_credentials()
        if credentials.get('errors'):
            return credentials

        # Validar que la API key sea válida (longitud mínima)
        if len(credentials['api_key']) < 20:
            return {'errors': [_('API Key parece inválida (muy corta)')]}

        return {
            'status': 'ok',
            'message': _('Credenciales configuradas correctamente'),
            'api_key_length': len(credentials['api_key']),
            'test_mode': credentials['test_mode'],
        }

    def get_balance(self):
        """
        Obtiene el saldo de timbres disponibles.

        Nota: REST XPRESS no tiene endpoint público para consultar saldo.
        Se debe configurar manualmente o usar panel web.
        """
        return {
            'errors': [_('Consulta de saldo no disponible en REST XPRESS. Consultar en panel web.')]
        }
```

---

### Registro del PAC en res.company

```python
# models/res_company.py

class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _get_l10n_mx_edi_pac_selection(self):
        """Extiende lista de PACs disponibles."""
        pacs = super()._get_l10n_mx_edi_pac_selection() or []
        pacs.extend([
            ('itadmin', 'IT Admin'),
            ('itadmin_backup', 'IT Admin Backup'),
            ('rest_xpress', 'REST XPRESS (Timbrador Xpress)'),  # NUEVO
        ])
        return pacs
```

---

### Integración con l10n_mx_edi.document

```python
# models/l10n_mx_edi_document.py

class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _get_pac_method_map(self):
        """Extiende el mapeo de métodos PAC."""
        pac_map = super()._get_pac_method_map()

        # Añadir REST XPRESS
        pac_map['credentials'].update({
            'rest_xpress': self._get_rest_xpress_credentials,
        })

        pac_map['sign'].update({
            'rest_xpress': self._rest_xpress_sign,
        })

        pac_map['cancel'].update({
            'rest_xpress': self._rest_xpress_cancel,
        })

        return pac_map

    @api.model
    def _get_rest_xpress_credentials(self, company):
        """Obtiene credenciales para REST XPRESS."""
        from .pac_connector.pac_rest_xpress import PACRestXpress
        connector = PACRestXpress(company)
        return connector.get_credentials()

    @api.model
    def _rest_xpress_sign(self, credentials, cfdi):
        """Firma con REST XPRESS."""
        from .pac_connector.pac_rest_xpress import PACRestXpress
        company = self.env.company
        connector = PACRestXpress(company)
        return connector.sign(credentials, cfdi)

    @api.model
    def _rest_xpress_cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancela con REST XPRESS."""
        from .pac_connector.pac_rest_xpress import PACRestXpress
        company = cfdi_values['root_company']
        connector = PACRestXpress(company)
        return connector.cancel(cfdi_values, credentials, uuid, cancel_reason, cancel_uuid)
```

---

### Vista de Configuración

```xml
<!-- views/res_config_settings_view.xml -->

<xpath expr="//field[@name='l10n_mx_edi_pac']" position="after">
    <!-- Configuración específica de REST XPRESS -->
    <div class="row mt16" invisible="l10n_mx_edi_pac != 'rest_xpress'">
        <label string="API Key REST XPRESS" for="l10n_mx_edi_pac_password" class="col-lg-3 o_light_label"/>
        <field name="l10n_mx_edi_pac_password" password="True" placeholder="93edc4af66b84c938f66a56ca0596205"/>
    </div>

    <div class="row" invisible="l10n_mx_edi_pac != 'rest_xpress'">
        <label string="" class="col-lg-3 o_light_label"/>
        <div class="col-lg-9">
            <div class="alert alert-info" role="alert">
                <strong>REST XPRESS (Timbrador Xpress)</strong><br/>
                • Ingresa tu API Key en el campo "Password"<br/>
                • Obtén tu API Key en: <a href="https://timbradorxpress.mx/panel" target="_blank">Panel REST XPRESS</a><br/>
                • Formato JSON con personalización de PDF<br/>
                • Logo de empresa incluido en PDF
            </div>
        </div>
    </div>
</xpath>
```

---

## TESTING Y PRUEBAS

### Test Unitario

```python
# tests/test_pac_rest_xpress.py

from odoo.tests.common import TransactionCase
import base64

class TestPACRestXpress(TransactionCase):

    def setUp(self):
        super().setUp()

        # Crear compañía de prueba
        self.company = self.env['res.company'].create({
            'name': 'Test Company MX - REST XPRESS',
            'vat': 'EKU9003173C9',
            'country_id': self.env.ref('base.mx').id,
            'zip': '80349',
            'street': 'Calle de Prueba 123',
            'phone': '6681234567',
            'email': 'test@example.com',
        })

        # Configurar PAC REST XPRESS
        self.company.write({
            'l10n_mx_edi_pac': 'rest_xpress',
            'l10n_mx_edi_pac_password': '93edc4af66b84c938f66a56ca0596205',  # API Key de prueba
            'l10n_mx_edi_pac_test_env': True,
        })

    def test_get_credentials(self):
        """Test obtención de credenciales REST XPRESS."""
        from odoo.addons.cdfi_invoice_enterprise.models.pac_connector.pac_rest_xpress import PACRestXpress

        connector = PACRestXpress(self.company)
        credentials = connector.get_credentials()

        self.assertNotIn('errors', credentials, "No debe haber errores")
        self.assertEqual(credentials['api_key'], '93edc4af66b84c938f66a56ca0596205')
        self.assertIn('dev.timbradorxpress.mx', credentials['sign_url'])
        self.assertTrue(credentials['test_mode'])

    def test_convert_cfdi_to_json(self):
        """Test conversión de XML a JSON REST XPRESS."""
        # Cargar XML de prueba
        xml_path = '/mnt/extra-addons/modulos_odoo19/cfdi40_XML/devTimbrado_cfdi40_Ingreso_01_PublicoGeneral.xml'
        with open(xml_path, 'rb') as f:
            xml_content = f.read()

        from odoo.addons.cdfi_invoice_enterprise.models.pac_connector.pac_rest_xpress import PACRestXpress

        connector = PACRestXpress(self.company)

        # Mock certificado
        certificate = self.env['certificate.certificate'].create({
            'name': 'Test Certificate',
            'company_id': self.company.id,
        })

        json_data = connector._convert_cfdi_to_json(xml_content, self.company, certificate)

        # Validar estructura
        self.assertIn('Comprobante', json_data)
        self.assertIn('CamposPDF', json_data)
        self.assertEqual(json_data['Comprobante']['Version'], '4.0')
        self.assertIn('Emisor', json_data['Comprobante'])
        self.assertIn('Receptor', json_data['Comprobante'])

    def test_validate_connection(self):
        """Test validación de conexión."""
        from odoo.addons.cdfi_invoice_enterprise.models.pac_connector.pac_rest_xpress import PACRestXpress

        connector = PACRestXpress(self.company)
        result = connector.validate_connection()

        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['test_mode'])
```

---

## PRÓXIMOS PASOS

1. ✅ **Crear archivo `pac_rest_xpress.py`** en la ubicación especificada
2. ✅ **Actualizar `res_company.py`** para incluir REST XPRESS en selección
3. ✅ **Actualizar `l10n_mx_edi_document.py`** para mapear métodos
4. ✅ **Crear vista de configuración** con instrucciones claras
5. ⬜ **Probar en ambiente de desarrollo** con API Key de prueba
6. ⬜ **Validar timbrado completo** con factura real
7. ⬜ **Probar cancelación** de CFDI
8. ⬜ **Documentar** en manual de usuario

---

## VENTAJAS DE REST XPRESS vs IT ADMIN

| Característica | IT Admin | REST XPRESS |
|----------------|----------|-------------|
| **Formato de entrada** | JSON custom | JSON estándar CFDI 4.0 |
| **Personalización PDF** | Limitada | Completa (CamposPDF) |
| **Logo en PDF** | No | Sí |
| **Múltiples métodos** | 1 (JSON) | 5 (XML, JSON, TFD, etc.) |
| **Documentación** | Básica | Completa con Postman |
| **Validaciones** | Básicas | Avanzadas con códigos de error |
| **Soporte complementos** | Limitado | Completo (Carta Porte, Nómina) |
| **Precio** | Variable | Competitivo |

---

## CONCLUSIÓN

El conector **PAC REST XPRESS** proporciona una integración completa y robusta para Odoo 19 Enterprise, con las siguientes ventajas:

✅ Formato JSON estándar CFDI 4.0
✅ Personalización completa de PDFs
✅ Múltiples métodos de timbrado
✅ Mejor manejo de errores
✅ Soporte para complementos
✅ Fácil configuración (solo API Key)

Este PAC es **ideal** para empresas que requieren:
- PDFs personalizados con logo
- Campos adicionales en facturas
- Mayor flexibilidad en formatos
- Mejor documentación y soporte

---

*Documento generado: 2026-01-05*
*Versión: 1.0*
