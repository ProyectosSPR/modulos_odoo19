# PLAN DE IMPLEMENTACIÓN: MIGRACIÓN A ODOO 19 ENTERPRISE
## Módulos CFDI México - cdfi_invoice + l10n_mx_sat_sync_itadmin

---

## RESUMEN EJECUTIVO

Este documento detalla el plan de migración de los módulos comunitarios de facturación electrónica mexicana (CFDI) hacia una arquitectura compatible con Odoo 19 Enterprise, incluyendo:

1. **Compatibilidad con Enterprise**: Adaptación de cdfi_invoice para coexistir con l10n_mx_edi
2. **Sistema Multi-PAC**: Implementación de múltiples proveedores de certificación (PACs)
3. **Dependencias resueltas**: Clarificación y optimización de dependencias entre módulos
4. **Actualización a CFDI 4.0**: Garantizar cumplimiento total con especificaciones SAT

---

## TABLA DE CONTENIDOS

1. [Análisis de Situación Actual](#1-análisis-de-situación-actual)
2. [Objetivos del Proyecto](#2-objetivos-del-proyecto)
3. [Arquitectura Propuesta](#3-arquitectura-propuesta)
4. [Análisis de Dependencias](#4-análisis-de-dependencias)
5. [Plan de Migración Detallado](#5-plan-de-migración-detallado)
6. [Implementación Multi-PAC](#6-implementación-multi-pac)
7. [Integración con Enterprise](#7-integración-con-enterprise)
8. [Plan de Pruebas](#8-plan-de-pruebas)
9. [Cronograma de Implementación](#9-cronograma-de-implementación)
10. [Riesgos y Mitigación](#10-riesgos-y-mitigación)

---

## 1. ANÁLISIS DE SITUACIÓN ACTUAL

### 1.1 Estado de los Módulos

#### **cdfi_invoice** (Versión 19.1.6)
- **Propósito**: Generación y timbrado de CFDI para Odoo Community
- **PAC Actual**: IT Admin (servidor único con respaldo)
- **Arquitectura**: Monolítica con PAC hardcodeado
- **CFDI Version**: 4.0 (completo)
- **Dependencias**: `sale`, `account`, `account_edi`, `purchase`, `base_vat`

**Limitaciones Actuales**:
```python
# Archivo: models/res_company.py
proveedor_timbrado = fields.Selection(
    selection=[('servidor', 'Principal'),
               ('servidor2', 'Respaldo')],  # Solo 2 opciones hardcodeadas
    string='Servidor de timbrado', default='servidor'
)

# URLs hardcodeadas en múltiples métodos:
if self.proveedor_timbrado == 'servidor':
    url = 'https://facturacion.itadmin.com.mx/api/saldo'
elif self.proveedor_timbrado == 'servidor2':
    url = 'https://facturacion2.itadmin.com.mx/api/validarcsd'
```

**Funcionalidades Implementadas**:
- ✅ Generación CFDI 4.0
- ✅ Timbrado con PAC IT Admin
- ✅ Cancelación de CFDI
- ✅ Complemento de pago (CEP)
- ✅ Facturas globales
- ✅ CFDIs relacionados
- ✅ Validación de certificados CSD
- ✅ Gestión de saldo de timbres
- ✅ Alarmas de vencimiento
- ✅ Generación de PDF con QR
- ✅ Catálogos SAT (Forma pago, Uso CFDI, Régimen fiscal, Unidades)

#### **l10n_mx_sat_sync_itadmin** (Versión 18.0.1.0.0)
- **Propósito**: Descarga e importación de XMLs desde el SAT
- **Métodos**: API SOAP (DescargaMasiva) + Web Scraping
- **FIEL**: Gestión completa de certificados electrónicos
- **Dependencias**: `account`, `purchase`
- **Dependencia oculta**: `cdfi_invoice` (comentada en manifest)

**Funcionalidades Implementadas**:
- ✅ Descarga masiva desde SAT (API SOAP)
- ✅ Descarga web (portal SAT con CAPTCHA)
- ✅ Parsing de XMLs CFDI
- ✅ Importación automática a facturas
- ✅ Reconciliación con facturas locales
- ✅ Clasificación de CFDIs (I, SI, E, SE, P, SP, N, SN, T, ST)
- ✅ Gestión de certificados FIEL
- ✅ Tareas programadas (CRON)

### 1.2 Odoo 19 Enterprise - l10n_mx_edi

**Arquitectura Enterprise**:
```
l10n_mx_edi/
├── models/
│   ├── account_edi_format.py          # Base abstracta EDI
│   ├── l10n_mx_edi_document.py        # Gestión de documentos CFDI
│   ├── account_move.py                # Extensión de facturas
│   ├── res_company.py                 # Configuración PAC
│   └── ...
├── PACs Nativos:
│   ├── Finkok (Quadrum)               # SOAP WSDL
│   ├── Solucion Factible              # SOAP WSDL
│   └── SW (Sapien SmarterWEB)         # REST + JWT
```

**Ventajas Enterprise**:
- Sistema multi-PAC extensible
- Integración nativa con account.edi
- Documentos EDI gestionados automáticamente
- Validaciones SAT integradas
- Soporte completo de complementos

---

## 2. OBJETIVOS DEL PROYECTO

### 2.1 Objetivos Principales

1. **Compatibilidad Enterprise**
   - Permitir que cdfi_invoice coexista con l10n_mx_edi
   - Opción de usar PACs Enterprise + PACs custom
   - Migración gradual sin pérdida de funcionalidad

2. **Sistema Multi-PAC**
   - Arquitectura extensible para añadir PACs
   - Configuración por empresa/journal
   - Failover automático entre PACs

3. **Resolución de Dependencias**
   - Clarificar relación cdfi_invoice ↔ l10n_mx_sat_sync
   - Eliminar acoplamiento innecesario
   - Modularización por funcionalidad

4. **Actualización Odoo 19**
   - Compatibilidad total con API 19.0
   - Aprovechamiento de nuevas features
   - Deprecación de código obsoleto

### 2.2 Objetivos Específicos

**Funcionales**:
- Añadir mínimo 2 PACs adicionales (Finkok, SW)
- Implementar selector de PAC por empresa
- Mantener compatibilidad con IT Admin PAC
- Importación automática de XMLs SAT

**Técnicos**:
- Refactorizar arquitectura a patrón Strategy (PACs)
- Implementar account.edi.format para cdfi_invoice
- Separar lógica de negocio de conectores PAC
- Unit tests para cada PAC (>80% coverage)

**De Negocio**:
- Reducción de dependencia de un solo proveedor
- Posibilidad de negociar mejores tarifas
- Redundancia y alta disponibilidad
- Flexibilidad para clientes finales

---

## 3. ARQUITECTURA PROPUESTA

### 3.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                    ODOO 19 ENTERPRISE                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │            account.edi.format (Base)                      │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│         ┌──────────────┴──────────────┬─────────────────────┐   │
│         │                             │                     │   │
│  ┌──────▼──────┐              ┌───────▼───────┐    ┌────────▼──────┐
│  │ l10n_mx_edi │              │cdfi_invoice_  │    │  Otros EDI    │
│  │ (Enterprise)│              │enterprise     │    │  formatos     │
│  └──────┬──────┘              └───────┬───────┘    └───────────────┘
│         │                             │                             │
│  ┌──────▼──────────────────────────────▼──────┐                    │
│  │     l10n_mx_edi.document (Shared)          │                    │
│  │  - _get_pac_method_map()                   │                    │
│  │  - _send_api()                             │                    │
│  │  - _cancel_api()                           │                    │
│  └──────┬─────────────────────────────────────┘                    │
│         │                                                           │
│  ┌──────▼──────────────────────────────────────────────┐           │
│  │         PAC Connector Layer (Pluggable)             │           │
│  │  ┌────────┐  ┌──────────┐  ┌──────┐  ┌──────────┐  │           │
│  │  │ Finkok │  │ Solfact  │  │  SW  │  │ IT Admin │  │           │
│  │  │ (SOAP) │  │  (SOAP)  │  │(REST)│  │  (REST)  │  │           │
│  │  └────────┘  └──────────┘  └──────┘  └──────────┘  │           │
│  │                                                     │           │
│  │  Patrón Strategy: cada PAC implementa:             │           │
│  │  - get_credentials()                               │           │
│  │  - sign()                                          │           │
│  │  - cancel()                                        │           │
│  └─────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              MÓDULO INDEPENDIENTE                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │   l10n_mx_sat_sync (Descarga SAT)                         │  │
│  │   - Independiente de PAC                                  │  │
│  │   - Solo requiere FIEL                                    │  │
│  │   - Importa a account.move estándar                       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Estructura de Módulos Propuesta

```
/mnt/extra-addons/modulos_odoo19/
├── cdfi_invoice/                      # Mantener para Community
│   ├── (código actual)
│   └── README.md → "Deprecado, usar cdfi_invoice_enterprise"
│
├── cdfi_invoice_enterprise/           # NUEVO - Principal para Enterprise
│   ├── __manifest__.py
│   │   depends: ['account_accountant', 'l10n_mx', 'l10n_mx_edi', 'certificate']
│   ├── models/
│   │   ├── account_edi_format.py      # Hereda de l10n_mx_edi
│   │   ├── res_company.py             # Config PAC multi
│   │   ├── res_config_settings.py     # UI configuración
│   │   └── pac_connector/             # NUEVO
│   │       ├── __init__.py
│   │       ├── pac_base.py            # Clase abstracta
│   │       ├── pac_itadmin.py         # IT Admin (migrado)
│   │       ├── pac_finkok.py          # Finkok
│   │       ├── pac_sw.py              # SW
│   │       └── pac_solfact.py         # Solucion Factible
│   ├── data/
│   │   └── catalogo.*.csv             # Catálogos SAT
│   └── views/
│       └── res_config_settings_view.xml
│
├── l10n_mx_sat_sync/                  # Renombrado (sin _itadmin)
│   ├── __manifest__.py
│   │   depends: ['account', 'purchase', 'certificate']
│   │   NO depende de cdfi_invoice ni l10n_mx_edi
│   ├── models/
│   │   ├── esignature.py → DEPRECATED (usar certificate.certificate)
│   │   ├── sat_api_import.py          # API SOAP SAT
│   │   ├── portal_sat.py              # Web scraping
│   │   ├── ir_attachment.py           # Parsing XML
│   │   └── res_company.py             # Descargas
│   └── wizard/
│       └── cfdi_invoice.py            # Importación genérica
│
└── l10n_mx_edi_extension/             # NUEVO (Opcional)
    ├── __manifest__.py
    │   depends: ['l10n_mx_edi']
    ├── models/
    │   └── l10n_mx_edi_document.py    # Extensiones para Enterprise
    └── (mejoras específicas Enterprise)
```

### 3.3 Patrón de Diseño: Strategy Pattern para PACs

```python
# models/pac_connector/pac_base.py
from abc import ABC, abstractmethod

class PACConnector(ABC):
    """Clase base abstracta para conectores PAC."""

    def __init__(self, company):
        self.company = company
        self.env = company.env

    @abstractmethod
    def get_credentials(self):
        """Retorna diccionario con credenciales del PAC.

        Returns:
            dict: {'username': str, 'password': str, 'url': str, ...}
                  o {'errors': [lista de errores]}
        """
        pass

    @abstractmethod
    def sign(self, credentials, cfdi_str):
        """Envía CFDI al PAC para timbrado.

        Args:
            credentials (dict): Credenciales obtenidas de get_credentials()
            cfdi_str (bytes): XML del CFDI firmado localmente

        Returns:
            dict: {'cfdi_str': bytes}  # CFDI timbrado
                  o {'errors': [lista de errores]}
        """
        pass

    @abstractmethod
    def cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancela CFDI en el PAC.

        Args:
            cfdi_values (dict): Valores del CFDI
            credentials (dict): Credenciales del PAC
            uuid (str): UUID a cancelar
            cancel_reason (str): Motivo ('01', '02', '03', '04')
            cancel_uuid (str): UUID de sustitución (opcional)

        Returns:
            dict: {}  # Éxito
                  o {'errors': [lista de errores]}
        """
        pass

    def validate_connection(self):
        """Valida conectividad con PAC (opcional)."""
        credentials = self.get_credentials()
        if credentials.get('errors'):
            return credentials
        # Implementar ping o validación según PAC
        return {'status': 'ok'}
```

```python
# models/pac_connector/pac_itadmin.py
from . import pac_base
import requests
import json
import base64

class PACITAdmin(pac_base.PACConnector):
    """Conector para PAC IT Admin (migrado de cdfi_invoice)."""

    def get_credentials(self):
        company = self.company

        if not company.l10n_mx_edi_pac_username or not company.l10n_mx_edi_pac_password:
            return {'errors': ['Faltan credenciales del PAC IT Admin']}

        # Determinar servidor
        server_type = company.l10n_mx_edi_pac_username  # 'servidor' o 'servidor2'

        if server_type == 'servidor':
            base_url = 'https://facturacion.itadmin.com.mx/api'
        elif server_type == 'servidor2':
            base_url = 'https://facturacion2.itadmin.com.mx/api'
        else:
            return {'errors': [f'Servidor inválido: {server_type}']}

        return {
            'api_key': company.l10n_mx_edi_pac_password,
            'rfc': company.vat,
            'modo_prueba': company.l10n_mx_edi_pac_test_env,
            'sign_url': f'{base_url}/invoice',
            'cancel_url': f'{base_url}/refund',
            'saldo_url': f'{base_url}/saldo',
            'validate_url': f'{base_url}/validarcsd',
        }

    def sign(self, credentials, cfdi_str):
        """Timbrado con IT Admin (REST JSON)."""

        # Convertir cfdi_str (bytes) a estructura JSON esperada por IT Admin
        # (migrar lógica de to_json() de account_invoice.py)

        url = credentials['sign_url']
        payload = {
            'factura': { ... },  # Datos del CFDI
            'emisor': { ... },
            'receptor': { ... },
            'informacion': {
                'cfdi': '4.0',
                'sistema': 'odoo19',
                'api_key': credentials['api_key'],
                'modo_prueba': credentials['modo_prueba'],
            },
            'lineas': [ ... ],
        }

        try:
            response = requests.post(
                url,
                auth=None,
                data=json.dumps(payload),
                headers={"Content-type": "application/json"},
                timeout=20
            )
            json_response = response.json()
        except Exception as e:
            return {'errors': [f'Error conectando con IT Admin: {str(e)}']}

        estado = json_response.get('estado_factura')
        if estado == 'factura_correcta':
            cfdi_signed = base64.b64decode(json_response['factura_xml'])
            return {'cfdi_str': cfdi_signed}
        else:
            error_msg = json_response.get('problemas_message', 'Error desconocido')
            return {'errors': [f'IT Admin rechazó timbrado: {error_msg}']}

    def cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancelación con IT Admin."""

        url = credentials['cancel_url']
        payload = {
            'rfc': credentials['rfc'],
            'uuid': uuid,
            'folio': cfdi_values.get('folio', ''),
            'serie': cfdi_values.get('serie', ''),
            'motivo': cancel_reason,
            'folio_sustitucion': cancel_uuid or '',
        }

        try:
            response = requests.post(
                url,
                data=json.dumps(payload),
                headers={"Content-type": "application/json"},
                timeout=20
            )
            json_response = response.json()
        except Exception as e:
            return {'errors': [f'Error cancelando en IT Admin: {str(e)}']}

        if json_response.get('estado') == 'cancelada':
            return {}  # Éxito
        else:
            return {'errors': [json_response.get('mensaje', 'Error en cancelación')]}
```

```python
# models/res_company.py (cdfi_invoice_enterprise)
from odoo import fields, models, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Extender selección de PAC de Enterprise
    @api.model
    def _get_l10n_mx_edi_pac_selection(self):
        """Extiende lista de PACs disponibles."""
        pacs = super()._get_l10n_mx_edi_pac_selection() or []
        pacs.extend([
            ('itadmin', 'IT Admin'),
            ('itadmin_backup', 'IT Admin Backup'),
            # Agregar más PACs custom aquí
        ])
        return pacs

    # Sobrescribir campo para incluir nuevos PACs
    l10n_mx_edi_pac = fields.Selection(
        selection='_get_l10n_mx_edi_pac_selection',
        string='PAC',
        help='Proveedor Autorizado de Certificación',
    )

    # Campos específicos para PACs custom
    l10n_mx_edi_pac_itadmin_server = fields.Selection([
        ('servidor', 'Principal'),
        ('servidor2', 'Respaldo'),
    ], string='Servidor IT Admin', default='servidor')
```

```python
# models/account_edi_format.py (cdfi_invoice_enterprise)
from odoo import models

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _get_pac_connector(self, company):
        """Factory para obtener instancia del conector PAC correcto."""
        pac_name = company.l10n_mx_edi_pac

        pac_map = {
            'finkok': 'pac_connector.pac_finkok.PACFinkok',
            'solfact': 'pac_connector.pac_solfact.PACSolfact',
            'sw': 'pac_connector.pac_sw.PACSW',
            'itadmin': 'pac_connector.pac_itadmin.PACITAdmin',
            'itadmin_backup': 'pac_connector.pac_itadmin.PACITAdmin',
        }

        connector_class_path = pac_map.get(pac_name)
        if not connector_class_path:
            raise ValueError(f'PAC no soportado: {pac_name}')

        # Importar dinámicamente
        module_path, class_name = connector_class_path.rsplit('.', 1)
        module = __import__(f'odoo.addons.cdfi_invoice_enterprise.models.{module_path}',
                           fromlist=[class_name])
        connector_class = getattr(module, class_name)

        return connector_class(company)
```

---

## 4. ANÁLISIS DE DEPENDENCIAS

### 4.1 Dependencias Actuales

#### **cdfi_invoice → Otros Módulos**
```python
# __manifest__.py
'depends': [
    'sale',          # ✅ Necesario (órdenes de venta)
    'account',       # ✅ Necesario (facturas)
    'account_edi',   # ✅ Necesario (EDI framework)
    'purchase',      # ✅ Necesario (órdenes de compra)
    'base_vat',      # ✅ Necesario (validación RFC)
]
```

**Análisis**:
- ✅ Todas las dependencias son legítimas
- ✅ No hay acoplamiento con l10n_mx_sat_sync
- ⚠️ `account_edi` es genérico, no específico de Enterprise

#### **l10n_mx_sat_sync_itadmin → Otros Módulos**
```python
# __manifest__.py
'depends': [
    'account',       # ✅ Necesario (facturas)
    'purchase',      # ✅ Necesario (facturas de compra)
    # 'cdfi_invoice',      # ❌ COMENTADO (dependencia incorrecta)
    # 'sale_purchase',     # ❌ COMENTADO (no existe en v19)
]
```

**Análisis**:
- ✅ Correctamente NO depende de cdfi_invoice
- ✅ Funciona independientemente (solo descarga XMLs)
- ⚠️ Tiene su propio modelo de certificados (duplicado)
- ⚠️ Catálogos SAT no están disponibles (podrían compartirse)

**¿Por qué parecen dependientes?**:

1. **Catálogos SAT Compartidos**:
   - cdfi_invoice define: `catalogo.forma.pago`, `catalogo.uso.cfdi`, etc.
   - l10n_mx_sat_sync los referencia en `ir_attachment.py`
   - **Solución**: Mover catálogos a módulo base `l10n_mx_catalogs`

2. **Modelo de Certificados**:
   - cdfi_invoice usa: `res.company` (archivo_cer, archivo_key, contrasena)
   - l10n_mx_sat_sync usa: `l10n.mx.esignature.certificate`
   - **Solución**: Usar `certificate.certificate` de Enterprise

3. **UUID en Facturas**:
   - cdfi_invoice almacena: `folio_fiscal` en `account.move`
   - l10n_mx_sat_sync almacena: `l10n_mx_edi_cfdi_uuid` en `account.move`
   - **Solución**: Unificar campo (usar estándar Enterprise)

### 4.2 Propuesta de Dependencias Optimizadas

```
┌─────────────────────────────────────────────────────────────┐
│  l10n_mx_catalogs (NUEVO - Base compartida)                │
│  - catalogo.forma.pago                                     │
│  - catalogo.uso.cfdi                                       │
│  - catalogo.regimen.fiscal                                 │
│  - catalogo.unidad.medida                                  │
│  Depends: ['base']                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴─────────────┬──────────────────────┐
        │                            │                      │
┌───────▼─────────┐     ┌────────────▼──────┐   ┌──────────▼────────┐
│ l10n_mx         │     │ cdfi_invoice_     │   │ l10n_mx_sat_sync  │
│ (Enterprise)    │     │ enterprise        │   │                   │
│                 │     │                   │   │                   │
│ Depends:        │     │ Depends:          │   │ Depends:          │
│ - account       │     │ - l10n_mx_edi     │   │ - account         │
│                 │     │ - l10n_mx_catalogs│   │ - certificate     │
│                 │     │ - certificate     │   │ - l10n_mx_catalogs│
└─────────┬───────┘     └──────────┬────────┘   └───────────────────┘
          │                        │
          └────────────┬───────────┘
                       │
              ┌────────▼──────────┐
              │ l10n_mx_edi       │
              │ (Enterprise EDI)  │
              │                   │
              │ Depends:          │
              │ - account_        │
              │   accountant      │
              │ - l10n_mx         │
              │ - certificate     │
              └───────────────────┘
```

**Ventajas**:
- ✅ Catálogos compartidos (DRY)
- ✅ Certificados unificados (Enterprise `certificate`)
- ✅ Sin dependencias circulares
- ✅ Módulos intercambiables

---

## 5. PLAN DE MIGRACIÓN DETALLADO

### 5.1 Fase 1: Preparación y Análisis (Semana 1-2)

#### **Tarea 1.1: Crear módulo base de catálogos**
```bash
mkdir -p /mnt/extra-addons/modulos_odoo19/l10n_mx_catalogs/{models,data,security}
```

**Archivos a crear**:
- `__manifest__.py`
- `models/__init__.py`
- `models/catalogo_forma_pago.py`
- `models/catalogo_uso_cfdi.py`
- `models/catalogo_regimen_fiscal.py`
- `models/catalogo_unidad_medida.py`
- `data/catalogo.*.csv` (migrar de cdfi_invoice)
- `security/ir.model.access.csv`

**Código base**:
```python
# __manifest__.py
{
    'name': 'México - Catálogos SAT',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'description': '''
        Catálogos del SAT para facturación electrónica mexicana.
        Compartidos entre módulos de CFDI.
    ''',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/catalogo.forma.pago.csv',
        'data/catalogo.uso.cfdi.csv',
        'data/catalogo.regimen.fiscal.csv',
        'data/catalogo.unidad.medida.csv',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

#### **Tarea 1.2: Auditoría de código**
- [ ] Identificar todos los endpoints PAC en cdfi_invoice
- [ ] Listar campos custom en `account.move`
- [ ] Mapear métodos de timbrado/cancelación
- [ ] Identificar lógica de negocio vs. conector

#### **Tarea 1.3: Configurar entorno de desarrollo**
```bash
# Crear rama de desarrollo
cd /mnt/extra-addons/modulos_odoo19
git checkout -b feature/enterprise-migration

# Backup de módulos actuales
cp -r cdfi_invoice cdfi_invoice_backup_$(date +%Y%m%d)
cp -r l10n_mx_sat_sync_itadmin l10n_mx_sat_sync_backup_$(date +%Y%m%d)
```

### 5.2 Fase 2: Creación de cdfi_invoice_enterprise (Semana 3-4)

#### **Tarea 2.1: Estructura de directorios**
```bash
mkdir -p cdfi_invoice_enterprise/{models/pac_connector,data,views,wizard,security,static/description}
```

#### **Tarea 2.2: Implementar PAC Base (Abstract)**

**Archivo**: `models/pac_connector/pac_base.py`
```python
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from odoo import _

class PACConnector(ABC):
    """
    Clase base abstracta para conectores de Proveedores Autorizados de Certificación (PAC).

    Todos los PACs deben implementar esta interfaz para garantizar compatibilidad.
    """

    def __init__(self, company):
        """
        Inicializa el conector PAC.

        Args:
            company (res.company): Registro de la compañía
        """
        self.company = company
        self.env = company.env

    @abstractmethod
    def get_credentials(self):
        """
        Obtiene las credenciales de acceso al PAC.

        Returns:
            dict: Credenciales con estructura específica del PAC
                  Debe incluir 'errors' si hay problemas

        Ejemplo:
            {
                'username': 'user@example.com',
                'password': 'secret',
                'sign_url': 'https://pac.example.com/sign',
                'cancel_url': 'https://pac.example.com/cancel',
            }

            o en caso de error:

            {'errors': ['Usuario no configurado', 'Password vacío']}
        """
        pass

    @abstractmethod
    def sign(self, credentials, cfdi_str):
        """
        Envía el CFDI al PAC para ser timbrado.

        Args:
            credentials (dict): Credenciales retornadas por get_credentials()
            cfdi_str (bytes): XML del CFDI ya firmado localmente con CSD

        Returns:
            dict: {'cfdi_str': bytes} con el CFDI timbrado (incluye TimbreFiscalDigital)
                  o {'errors': [lista de errores]}
        """
        pass

    @abstractmethod
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
        pass

    def validate_connection(self):
        """
        Valida la conexión con el PAC (método opcional).

        Returns:
            dict: {'status': 'ok'} si la conexión es exitosa
                  o {'errors': [lista de errores]}
        """
        credentials = self.get_credentials()
        if credentials.get('errors'):
            return credentials

        return {'status': 'ok', 'message': _('Conexión no validada (implementar en subclase)')}

    def get_balance(self):
        """
        Obtiene el saldo de timbres disponibles (método opcional).

        Returns:
            dict: {'balance': float, 'expiry_date': date}
                  o {'errors': [lista de errores]}
        """
        return {'errors': [_('Consulta de saldo no implementada para este PAC')]}
```

#### **Tarea 2.3: Migrar PAC IT Admin**

**Archivo**: `models/pac_connector/pac_itadmin.py`

(Migrar lógica de `cdfi_invoice/models/res_company.py` y `account_invoice.py`)

**Pasos**:
1. Extraer lógica de `to_json()` de `account_invoice.py`
2. Adaptar a método `sign()`
3. Migrar lógica de cancelación
4. Implementar `get_balance()` (método `get_saldo()`)

#### **Tarea 2.4: Implementar PAC Finkok**

**Archivo**: `models/pac_connector/pac_finkok.py`

```python
# -*- coding: utf-8 -*-
from . import pac_base
from zeep import Client
from odoo import _
import base64

class PACFinkok(pac_base.PACConnector):
    """Conector para PAC Finkok (Quadrum) - SOAP."""

    def get_credentials(self):
        company = self.company

        if company.l10n_mx_edi_pac_test_env:
            return {
                'username': 'cfdi@vauxoo.com',
                'password': 'vAux00__',
                'sign_url': 'http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl',
                'cancel_url': 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl',
            }
        else:
            if not company.l10n_mx_edi_pac_username or not company.l10n_mx_edi_pac_password:
                return {'errors': [_('Faltan credenciales de Finkok')]}

            return {
                'username': company.sudo().l10n_mx_edi_pac_username,
                'password': company.sudo().l10n_mx_edi_pac_password,
                'sign_url': 'http://facturacion.finkok.com/servicios/soap/stamp.wsdl',
                'cancel_url': 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl',
            }

    def sign(self, credentials, cfdi_str):
        """Timbrado SOAP con Finkok."""
        try:
            client = Client(credentials['sign_url'], timeout=20)
            response = client.service.stamp(
                cfdi_str.decode('utf-8'),
                credentials['username'],
                credentials['password']
            )
        except Exception as e:
            return {'errors': [_("Error Finkok: %s") % str(e)]}

        if response.Incidencias and not response.xml:
            error = response.Incidencias.Incidencia[0]
            errors = []
            if hasattr(error, 'CodigoError'):
                errors.append(_("Código: %s") % error.CodigoError)
            if hasattr(error, 'MensajeIncidencia'):
                errors.append(_("Mensaje: %s") % error.MensajeIncidencia)
            return {'errors': errors}

        cfdi_signed = getattr(response, 'xml', None)
        if cfdi_signed:
            return {'cfdi_str': cfdi_signed.encode('utf-8')}

        return {'errors': [_('Finkok no retornó XML')]}

    def cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancelación SOAP con Finkok."""
        company = cfdi_values['root_company']
        certificate_sudo = cfdi_values['certificate'].sudo()

        cer_pem = base64.b64decode(certificate_sudo.pem_certificate)
        key_pem = self._get_unencrypted_private_key_pem(certificate_sudo.private_key_id)

        try:
            client = Client(credentials['cancel_url'], timeout=20)
            factory = client.type_factory('apps.services.soap.core.views')

            uuid_type = factory.UUID()
            uuid_type.UUID = uuid
            uuid_type.Motivo = cancel_reason
            if cancel_uuid:
                uuid_type.FolioSustitucion = cancel_uuid

            docs_list = factory.UUIDArray(uuid_type)

            response = client.service.cancel(
                docs_list,
                credentials['username'],
                credentials['password'],
                company.vat,
                cer_pem,
                key_pem,
            )
        except Exception as e:
            return {'errors': [_("Error cancelando Finkok: %s") % str(e)]}

        # Procesar respuesta...
        if hasattr(response, 'CodEstatus') and response.CodEstatus in ('201', '202'):
            return {}  # Éxito

        return {'errors': [_('Cancelación rechazada por Finkok')]}

    def _get_unencrypted_private_key_pem(self, private_key):
        """Obtiene la llave privada desencriptada en formato PEM."""
        # Implementar según certificate module de Enterprise
        return private_key.get_unencrypted_key_pem()
```

#### **Tarea 2.5: Implementar PAC SW**

**Archivo**: `models/pac_connector/pac_sw.py`

(Similar a Finkok, pero con REST API en lugar de SOAP)

```python
# -*- coding: utf-8 -*-
from . import pac_base
import requests
import json
import base64
import random
import string
from odoo import _

class PACSW(pac_base.PACConnector):
    """Conector para PAC SW (Sapien SmarterWEB) - REST."""

    def _get_sw_token(self, credentials):
        """Obtiene token JWT de autenticación."""
        if credentials['password'] and not credentials['username']:
            # Token directo
            return {'token': credentials['password'].strip()}

        try:
            headers = {
                'user': credentials['username'],
                'password': credentials['password'],
                'Cache-Control': "no-cache"
            }
            response = requests.post(credentials['login_url'], headers=headers, timeout=20)
            response.raise_for_status()
            response_json = response.json()
            return {'token': response_json['data']['token']}
        except Exception as e:
            return {'errors': [str(e)]}

    def get_credentials(self):
        company = self.company

        if not company.l10n_mx_edi_pac_username or not company.l10n_mx_edi_pac_password:
            return {'errors': [_('Faltan credenciales de SW')]}

        credentials = {
            'username': company.sudo().l10n_mx_edi_pac_username,
            'password': company.sudo().l10n_mx_edi_pac_password,
        }

        if company.l10n_mx_edi_pac_test_env:
            credentials.update({
                'login_url': 'https://services.test.sw.com.mx/security/authenticate',
                'sign_url': 'https://services.test.sw.com.mx/cfdi33/stamp/v3/b64',
                'cancel_url': 'https://services.test.sw.com.mx/cfdi33/cancel/csd',
            })
        else:
            credentials.update({
                'login_url': 'https://services.sw.com.mx/security/authenticate',
                'sign_url': 'https://services.sw.com.mx/cfdi33/stamp/v3/b64',
                'cancel_url': 'https://services.sw.com.mx/cfdi33/cancel/csd',
            })

        # Obtener token
        token_result = self._get_sw_token(credentials)
        if token_result.get('errors'):
            return token_result

        credentials['token'] = token_result['token']
        return credentials

    def sign(self, credentials, cfdi_str):
        """Timbrado REST con SW."""
        cfdi_b64 = base64.encodebytes(cfdi_str).decode('UTF-8')

        # Crear boundary para multipart
        boundary = ''.join(random.choices(string.ascii_letters + string.digits, k=30))

        payload = f"""--{boundary}
Content-Type: text/xml
Content-Transfer-Encoding: binary
Content-Disposition: form-data; name="xml"; filename="xml"

{cfdi_b64}
--{boundary}--
"""
        payload = payload.replace('\n', '\r\n').encode('UTF-8')

        headers = {
            'Authorization': f"bearer {credentials['token']}",
            'Content-Type': f'multipart/form-data; boundary="{boundary}"',
        }

        try:
            response = requests.post(credentials['sign_url'], headers=headers, data=payload, timeout=20)
            response.raise_for_status()
            response_json = response.json()
        except Exception as e:
            return {'errors': [_('Error SW: %s') % str(e)]}

        try:
            cfdi_signed_b64 = response_json['data']['cfdi']
            cfdi_signed = base64.b64decode(cfdi_signed_b64)
            return {'cfdi_str': cfdi_signed}
        except (KeyError, TypeError):
            code = response_json.get('message', '')
            msg = response_json.get('messageDetail', '')
            return {'errors': [f"SW Code: {code}", f"SW Message: {msg}"]}

    def cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancelación REST con SW."""
        company = cfdi_values['root_company']
        certificate_sudo = cfdi_values['certificate'].sudo()

        headers = {
            'Authorization': f"bearer {credentials['token']}",
            'Content-Type': "application/json"
        }

        key_pem = self._get_unencrypted_private_key_pem(certificate_sudo.private_key_id)

        payload_dict = {
            'rfc': company.vat,
            'b64Cer': certificate_sudo.pem_certificate.decode('UTF-8'),
            'b64Key': base64.b64encode(key_pem).decode('UTF-8'),
            'password': certificate_sudo.private_key_id.password,
            'uuid': uuid,
            'motivo': cancel_reason,
        }

        if cancel_uuid:
            payload_dict['folioSustitucion'] = cancel_uuid

        payload = json.dumps(payload_dict)

        try:
            response = requests.post(credentials['cancel_url'], headers=headers, data=payload, timeout=20)
            response.raise_for_status()
            response_json = response.json()
        except Exception as e:
            return {'errors': [_('Error cancelando SW: %s') % str(e)]}

        if response_json.get('status') == 'success':
            return {}

        return {'errors': [response_json.get('message', 'Error desconocido')]}

    def _get_unencrypted_private_key_pem(self, private_key):
        """Obtiene llave privada PEM."""
        return private_key.get_unencrypted_key_pem()
```

#### **Tarea 2.6: Integrar con l10n_mx_edi.document**

**Archivo**: `models/l10n_mx_edi_document.py`

```python
# -*- coding: utf-8 -*-
from odoo import models, api

class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _get_pac_method_map(self):
        """Extiende el mapeo de métodos PAC con PACs custom."""
        pac_map = super()._get_pac_method_map()

        # Añadir PACs custom
        pac_map['credentials'].update({
            'itadmin': self._get_itadmin_credentials,
            'itadmin_backup': self._get_itadmin_credentials,
        })

        pac_map['sign'].update({
            'itadmin': self._itadmin_sign,
            'itadmin_backup': self._itadmin_sign,
        })

        pac_map['cancel'].update({
            'itadmin': self._itadmin_cancel,
            'itadmin_backup': self._itadmin_cancel,
        })

        return pac_map

    @api.model
    def _get_itadmin_credentials(self, company):
        """Obtiene credenciales para IT Admin usando el conector."""
        from .pac_connector.pac_itadmin import PACITAdmin
        connector = PACITAdmin(company)
        return connector.get_credentials()

    @api.model
    def _itadmin_sign(self, credentials, cfdi):
        """Firma con IT Admin usando el conector."""
        from .pac_connector.pac_itadmin import PACITAdmin
        # Nota: necesitamos company, la obtenemos del contexto
        company = self.env.company
        connector = PACITAdmin(company)
        return connector.sign(credentials, cfdi)

    @api.model
    def _itadmin_cancel(self, cfdi_values, credentials, uuid, cancel_reason, cancel_uuid=None):
        """Cancela con IT Admin usando el conector."""
        from .pac_connector.pac_itadmin import PACITAdmin
        company = cfdi_values['root_company']
        connector = PACITAdmin(company)
        return connector.cancel(cfdi_values, credentials, uuid, cancel_reason, cancel_uuid)
```

### 5.3 Fase 3: Refactorización de l10n_mx_sat_sync (Semana 5)

#### **Tarea 3.1: Renombrar módulo**
```bash
mv l10n_mx_sat_sync_itadmin l10n_mx_sat_sync
```

#### **Tarea 3.2: Actualizar manifest**
```python
# __manifest__.py
{
    'name': 'México - Sincronización SAT',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'description': '''
        Descarga e importación de CFDIs desde el portal del SAT.

        Características:
        - Descarga masiva mediante API SOAP (DescargaMasiva)
        - Descarga web mediante portal SAT
        - Parsing automático de XMLs
        - Importación a facturas Odoo
        - Reconciliación con facturas locales
    ''',
    'depends': [
        'account',
        'purchase',
        'certificate',              # NUEVO - usar certificados Enterprise
        'l10n_mx_catalogs',         # NUEVO - catálogos compartidos
    ],
    'external_dependencies': {
        'python': ['xmltodict', 'OpenSSL'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_mx_edi_esignature.xml',  # DEPRECAR si usa certificate
        'security/security.xml',
        'data/cron_data.xml',
        'views/ir_attachment_view.xml',
        'views/res_config_settings_view.xml',
        'views/res_company_view.xml',
        'views/solicitud_ws.xml',
        'wizard/cfdi_invoice.xml',
        'wizard/import_invoice_process_message.xml',
        'wizard/reconcile_vendor_cfdi_xml_bill.xml',
        'wizard/xml_invoice_reconcile_view.xml',
        'wizard/descarga_x_dia_wizard.xml',
        'wizard/attach_xmls_wizard_view.xml',
        'report/report_facturas_de_clientes_or_proveedores.xml',
        'report/payment_report_from_xml.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_mx_sat_sync/static/src/xml/*.xml',
            'l10n_mx_sat_sync/static/src/js/**/*',
            'l10n_mx_sat_sync/static/src/css/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

#### **Tarea 3.3: Migrar certificados a `certificate.certificate`**

**Archivo**: `models/res_company.py`

```python
# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    # DEPRECAR campo propio, usar campo de Enterprise
    # l10n_mx_esignature_ids = fields.One2many(...)  # ELIMINAR

    # Usar campo de l10n_mx_edi
    # l10n_mx_edi_certificate_ids ya existe en Enterprise

    # Métodos de descarga siguen igual, pero usan:
    # certificate = self.l10n_mx_edi_certificate_ids.filtered('is_valid')[:1]
```

#### **Tarea 3.4: Actualizar referencias a catálogos**

**Archivo**: `models/ir_attachment.py`

```python
# Cambiar:
# forma_pago = fields.Char(...)
#
# Por:
forma_pago_id = fields.Many2one('catalogo.forma.pago', string='Forma de pago')
methodo_pago = fields.Selection([('PUE', 'PUE'), ('PPD', 'PPD')])
uso_cfdi_id = fields.Many2one('catalogo.uso.cfdi', string='Uso CFDI')
# etc.
```

#### **Tarea 3.5: Unificar campo UUID**

**Archivo**: `wizard/cfdi_invoice.py`

```python
# Al importar facturas, usar campo estándar:
move_vals = {
    ...
    'l10n_mx_edi_cfdi_uuid': uuid,  # Campo de Enterprise
    # NO usar 'folio_fiscal' custom
}
```

### 5.4 Fase 4: Testing y Validación (Semana 6-7)

#### **Tarea 4.1: Unit Tests - PACs**

**Archivo**: `tests/test_pac_connectors.py`

```python
# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import base64

class TestPACConnectors(TransactionCase):

    def setUp(self):
        super().setUp()

        # Crear compañía de prueba
        self.company = self.env['res.company'].create({
            'name': 'Test Company MX',
            'vat': 'XIA190128J61',
            'country_id': self.env.ref('base.mx').id,
            'zip': '28000',
        })

        # Configurar certificado de prueba
        # (cargar certificados de prueba desde data/)

    def test_itadmin_credentials(self):
        """Test obtención de credenciales IT Admin."""
        from odoo.addons.cdfi_invoice_enterprise.models.pac_connector.pac_itadmin import PACITAdmin

        self.company.write({
            'l10n_mx_edi_pac': 'itadmin',
            'l10n_mx_edi_pac_username': 'servidor',
            'l10n_mx_edi_pac_password': 'test_api_key',
            'l10n_mx_edi_pac_test_env': True,
        })

        connector = PACITAdmin(self.company)
        credentials = connector.get_credentials()

        self.assertNotIn('errors', credentials, "No debe haber errores")
        self.assertEqual(credentials['api_key'], 'test_api_key')
        self.assertIn('facturacion.itadmin.com.mx', credentials['sign_url'])

    def test_finkok_credentials_test_env(self):
        """Test credenciales Finkok en ambiente de prueba."""
        from odoo.addons.cdfi_invoice_enterprise.models.pac_connector.pac_finkok import PACFinkok

        self.company.write({
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
        })

        connector = PACFinkok(self.company)
        credentials = connector.get_credentials()

        self.assertEqual(credentials['username'], 'cfdi@vauxoo.com')
        self.assertIn('demo-facturacion.finkok.com', credentials['sign_url'])

    def test_sw_token_generation(self):
        """Test generación de token SW."""
        # Implementar mock de requests para simular respuesta de SW
        pass

    def test_pac_factory(self):
        """Test factory de PACs."""
        doc_model = self.env['l10n_mx_edi.document']

        # IT Admin
        self.company.l10n_mx_edi_pac = 'itadmin'
        connector = doc_model._get_pac_connector(self.company)
        self.assertEqual(connector.__class__.__name__, 'PACITAdmin')

        # Finkok
        self.company.l10n_mx_edi_pac = 'finkok'
        connector = doc_model._get_pac_connector(self.company)
        self.assertEqual(connector.__class__.__name__, 'PACFinkok')
```

#### **Tarea 4.2: Integration Tests - Timbrado**

```python
class TestCFDIStamping(TransactionCase):

    def test_full_invoice_stamping_itadmin(self):
        """Test timbrado completo de factura con IT Admin."""
        # Crear factura
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2024-01-15',
            'company_id': self.company.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 1000,
            })],
        })
        invoice.action_post()

        # Configurar CFDI
        invoice.write({
            'factura_cfdi': True,
            'tipo_comprobante': 'I',
            'methodo_pago': 'PUE',
            'forma_pago_id': self.forma_pago_03.id,  # Transferencia
            'uso_cfdi_id': self.uso_g01.id,          # Adquisición
        })

        # Mock del servicio PAC
        # (usar vcr.py o responses library)

        # Timbrar
        invoice.action_cfdi_generate()

        # Validar resultado
        self.assertEqual(invoice.estado_factura, 'factura_correcta')
        self.assertTrue(invoice.folio_fiscal)
        self.assertTrue(len(invoice.folio_fiscal) == 36)  # UUID format
```

#### **Tarea 4.3: Integration Tests - Descarga SAT**

```python
class TestSATDownload(TransactionCase):

    def test_download_api_soap(self):
        """Test descarga por API SOAP."""
        # Mock de SOAP client
        pass

    def test_xml_parsing(self):
        """Test parsing de XML descargado."""
        # Cargar XML de prueba
        with open('tests/data/test_cfdi_invoice.xml', 'rb') as f:
            xml_content = f.read()

        attachment = self.env['ir.attachment'].create({
            'name': 'test_cfdi.xml',
            'datas': base64.b64encode(xml_content),
            'res_model': 'account.move',
            'res_id': 0,
        })

        # Validar parsing
        self.assertTrue(attachment.cfdi_uuid)
        self.assertEqual(attachment.cfdi_type, 'I')  # Factura de ingreso
```

### 5.5 Fase 5: Documentación y Deployment (Semana 8)

#### **Tarea 5.1: README.md**

Crear documentación completa:
- Guía de instalación
- Configuración de PACs
- Migración desde cdfi_invoice antiguo
- Troubleshooting

#### **Tarea 5.2: Guías de usuario**

- Manual de configuración de certificados
- Manual de timbrado
- Manual de descarga SAT
- Manual de reconciliación

#### **Tarea 5.3: Changelog**

Documentar cambios entre versiones:
- Breaking changes
- Nuevas funcionalidades
- Deprecaciones

---

## 6. IMPLEMENTACIÓN MULTI-PAC

### 6.1 Configuración en Odoo

**Vista de Configuración** (`views/res_config_settings_view.xml`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="res_config_settings_view_form" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.cdfi.enterprise</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="l10n_mx_edi.res_config_settings_view_form"/>
        <field name="arch" type="xml">

            <!-- Extender selector de PAC -->
            <xpath expr="//field[@name='l10n_mx_edi_pac']" position="attributes">
                <attribute name="options">{'no_create': True, 'no_open': True}</attribute>
            </xpath>

            <!-- Añadir configuración específica de IT Admin -->
            <xpath expr="//field[@name='l10n_mx_edi_pac']" position="after">
                <div class="row mt16" invisible="l10n_mx_edi_pac not in ['itadmin', 'itadmin_backup']">
                    <label string="Servidor IT Admin" for="l10n_mx_edi_pac_itadmin_server" class="col-lg-3 o_light_label"/>
                    <field name="l10n_mx_edi_pac_itadmin_server"/>
                </div>

                <div class="row" invisible="l10n_mx_edi_pac not in ['itadmin', 'itadmin_backup']">
                    <label string="API Key" for="l10n_mx_edi_pac_password" class="col-lg-3 o_light_label"/>
                    <field name="l10n_mx_edi_pac_password" password="True"/>
                </div>
            </xpath>

            <!-- Botón para validar conexión PAC -->
            <xpath expr="//div[@id='l10n_mx_edi_settings']" position="inside">
                <div class="row mt16">
                    <label string="Validar Conexión" class="col-lg-3 o_light_label"/>
                    <button name="validate_pac_connection" type="object" string="Probar Conexión" class="btn-link"/>
                </div>
            </xpath>

        </field>
    </record>
</odoo>
```

### 6.2 Selección Dinámica de PAC

**Por Empresa**:
```python
# res.company
company.l10n_mx_edi_pac = 'itadmin'  # Empresa A usa IT Admin
company.l10n_mx_edi_pac = 'finkok'   # Empresa B usa Finkok
```

**Failover Automático** (Opcional):

```python
# models/l10n_mx_edi_document.py

def _send_api_with_failover(self, company, ...):
    """Intenta timbrar con PAC principal, si falla usa backup."""

    primary_pac = company.l10n_mx_edi_pac
    backup_pac = company.l10n_mx_edi_pac_backup  # Nuevo campo

    # Intentar con PAC principal
    result = self._send_api(company, ...)

    if result.get('errors') and backup_pac:
        # Falló, intentar con backup
        company_temp = company.copy()
        company_temp.l10n_mx_edi_pac = backup_pac
        result = self._send_api(company_temp, ...)

        if not result.get('errors'):
            # Éxito con backup, notificar
            company.message_post(
                body=_("Timbrado realizado con PAC de respaldo: %s") % backup_pac
            )

    return result
```

### 6.3 Monitoreo de PACs

**Dashboard de PACs** (Opcional - Fase 2):

```python
# models/pac_monitor.py

class PACMonitor(models.Model):
    _name = 'l10n_mx.pac.monitor'
    _description = 'Monitor de PACs'

    pac_name = fields.Selection([
        ('finkok', 'Finkok'),
        ('solfact', 'Solucion Factible'),
        ('sw', 'SW'),
        ('itadmin', 'IT Admin'),
    ])

    company_id = fields.Many2one('res.company')

    # Métricas
    total_stamps = fields.Integer('Total Timbrados')
    failed_stamps = fields.Integer('Timbrados Fallidos')
    success_rate = fields.Float('Tasa de Éxito (%)', compute='_compute_success_rate')
    avg_response_time = fields.Float('Tiempo Promedio (seg)')

    # Última actividad
    last_stamp_date = fields.Datetime('Último Timbrado')
    last_error_date = fields.Datetime('Último Error')
    last_error_message = fields.Text('Mensaje de Error')

    def _compute_success_rate(self):
        for record in self:
            if record.total_stamps > 0:
                record.success_rate = ((record.total_stamps - record.failed_stamps) / record.total_stamps) * 100
            else:
                record.success_rate = 0
```

---

## 7. INTEGRACIÓN CON ENTERPRISE

### 7.1 Coexistencia con l10n_mx_edi

**Estrategia**: cdfi_invoice_enterprise **extiende** l10n_mx_edi, no lo reemplaza.

```python
# __manifest__.py de cdfi_invoice_enterprise
{
    'name': 'CFDI Invoice Enterprise',
    'depends': [
        'l10n_mx_edi',           # Base de Enterprise
        'l10n_mx',               # Localización mexicana
        'account_accountant',    # Contabilidad Enterprise
        'certificate',           # Certificados digitales
        'l10n_mx_catalogs',      # Catálogos compartidos
    ],
}
```

### 7.2 Uso de account.edi.format

```python
# models/account_edi_format.py

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _is_compatible_with_journal(self, journal):
        """Determinar si el formato EDI aplica al journal."""
        self.ensure_one()
        if self.code == 'cfdi_4_0':
            # Solo para journals mexicanos
            return journal.company_id.country_id.code == 'MX'
        return super()._is_compatible_with_journal(journal)

    def _get_move_applicability(self, move):
        """Definir aplicabilidad del formato EDI."""
        self.ensure_one()

        if self.code != 'cfdi_4_0':
            return super()._get_move_applicability(move)

        # Solo facturas de venta/compra en México
        if move.company_id.country_id.code != 'MX':
            return None

        if move.move_type not in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
            return None

        return {
            'post': self._cfdi_invoice_post,
            'cancel': self._cfdi_invoice_cancel,
            'edi_content': self._cfdi_get_xml_content,
        }

    def _cfdi_invoice_post(self, invoices):
        """Procesar facturas para envío a PAC."""
        for invoice in invoices:
            if not invoice.factura_cfdi:
                continue

            # Delegar a l10n_mx_edi.document
            invoice._l10n_mx_edi_cfdi_invoice_try_send()

        return {}

    def _cfdi_invoice_cancel(self, invoices):
        """Procesar cancelación de facturas."""
        for invoice in invoices:
            document = invoice.l10n_mx_edi_invoice_document_ids.filtered(
                lambda d: d.state == 'invoice_sent'
            )[:1]

            if document:
                invoice._l10n_mx_edi_cfdi_invoice_try_cancel(document, '02')

        return {}
```

### 7.3 Migración de Datos Existentes

**Script de Migración** (`migrations/19.0.1.0.0/post-migrate.py`):

```python
# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Migrar datos de cdfi_invoice antiguo a cdfi_invoice_enterprise."""

    if not version:
        return

    _logger.info('Iniciando migración de cdfi_invoice a Enterprise...')

    # 1. Migrar campo folio_fiscal a l10n_mx_edi_cfdi_uuid
    cr.execute("""
        UPDATE account_move
        SET l10n_mx_edi_cfdi_uuid = folio_fiscal
        WHERE folio_fiscal IS NOT NULL
          AND l10n_mx_edi_cfdi_uuid IS NULL
    """)

    _logger.info('Migrados %d UUIDs', cr.rowcount)

    # 2. Migrar configuración de PAC
    cr.execute("""
        UPDATE res_company
        SET l10n_mx_edi_pac = 'itadmin',
            l10n_mx_edi_pac_username = proveedor_timbrado,
            l10n_mx_edi_pac_password = api_key,
            l10n_mx_edi_pac_test_env = modo_prueba
        WHERE proveedor_timbrado IS NOT NULL
    """)

    _logger.info('Migradas %d configuraciones de PAC', cr.rowcount)

    # 3. Crear l10n_mx_edi.document para facturas timbradas
    cr.execute("""
        INSERT INTO l10n_mx_edi_document (
            move_id,
            datetime,
            state,
            attachment_uuid,
            create_date,
            write_date,
            create_uid,
            write_uid
        )
        SELECT
            id,
            fecha_certificacion::timestamp,
            CASE
                WHEN estado_factura = 'factura_correcta' THEN 'invoice_sent'
                WHEN estado_factura = 'factura_cancelada' THEN 'invoice_cancel'
                ELSE 'invoice_sent_failed'
            END,
            folio_fiscal,
            create_date,
            write_date,
            create_uid,
            write_uid
        FROM account_move
        WHERE folio_fiscal IS NOT NULL
          AND id NOT IN (SELECT move_id FROM l10n_mx_edi_document WHERE move_id IS NOT NULL)
    """)

    _logger.info('Creados %d documentos EDI', cr.rowcount)

    _logger.info('Migración completada exitosamente')
```

---

## 8. PLAN DE PRUEBAS

### 8.1 Test Plan Completo

| Categoría | Escenario | PAC | Ambiente | Prioridad |
|-----------|-----------|-----|----------|-----------|
| **Timbrado** | Factura simple (1 producto, IVA 16%) | IT Admin | Test | P0 |
|  | Factura simple | Finkok | Test | P0 |
|  | Factura simple | SW | Test | P0 |
|  | Factura múltiples productos | IT Admin | Test | P1 |
|  | Factura con descuento | IT Admin | Test | P1 |
|  | Factura moneda extranjera (USD) | IT Admin | Test | P1 |
|  | Factura global | IT Admin | Test | P2 |
|  | Factura con CFDIs relacionados | IT Admin | Test | P2 |
|  | Factura público general (XAXX010101000) | IT Admin | Test | P1 |
|  | Factura a extranjero (XEXX010101000) | IT Admin | Test | P2 |
| **Cancelación** | Cancelación motivo 02 (sin relación) | IT Admin | Test | P0 |
|  | Cancelación motivo 01 (con relación) | IT Admin | Test | P1 |
|  | Cancelación motivo 04 (sustitución) | IT Admin | Test | P2 |
| **Complementos** | Complemento de pago (PUE) | IT Admin | Test | P1 |
|  | Complemento de pago (PPD) | IT Admin | Test | P1 |
| **Descarga SAT** | Descarga por API SOAP | N/A | Producción | P0 |
|  | Descarga por web | N/A | Producción | P1 |
|  | Parsing XML recibido | N/A | N/A | P0 |
|  | Importación automática | N/A | N/A | P0 |
|  | Reconciliación exacta | N/A | N/A | P1 |
|  | Reconciliación por rango | N/A | N/A | P2 |
| **Failover** | Cambio automático de PAC | Multi | Test | P2 |
| **Performance** | Timbrado de 100 facturas | IT Admin | Test | P2 |
|  | Descarga de 1000 XMLs | N/A | Test | P2 |
| **Producción** | Timbrado real | IT Admin | Producción | P0 |
|  | Timbrado real | Finkok | Producción | P0 |
|  | Cancelación real | IT Admin | Producción | P0 |

### 8.2 Datos de Prueba

**Certificados de Prueba**:
- CSD de prueba SAT: `tests/data/CSD_Prueba_CFDI_LAN7008173R5.cer/key`
- FIEL de prueba: `tests/data/FIEL_Prueba_LAN7008173R5.cer/key`

**RFCs de Prueba**:
- Emisor: `LAN7008173R5` (Persona Moral genérica SAT)
- Receptor: `XAXX010101000` (Público general)
- Receptor: `XEXX010101000` (Extranjero)

**Productos de Prueba**:
```python
{
    'name': 'Producto de Prueba',
    'clave_producto': '01010101',  # Código SAT genérico
    'cat_unidad_medida': 'H87',    # Pieza
}
```

---

## 9. CRONOGRAMA DE IMPLEMENTACIÓN

### 9.1 Timeline Detallado

```
Semana 1-2: PREPARACIÓN
├── Día 1-2: Análisis de código actual
├── Día 3-4: Crear módulo l10n_mx_catalogs
├── Día 5-7: Diseñar arquitectura PAC
└── Día 8-10: Configurar entorno de desarrollo

Semana 3-4: DESARROLLO CORE
├── Día 11-13: Implementar pac_base.py (abstracto)
├── Día 14-16: Migrar PAC IT Admin
├── Día 17-19: Implementar PAC Finkok
├── Día 20-22: Implementar PAC SW
├── Día 23-24: Integrar con l10n_mx_edi.document
└── Día 25-28: UI y configuración

Semana 5: REFACTORIZACIÓN SAT SYNC
├── Día 29-30: Renombrar y actualizar manifest
├── Día 31-32: Migrar a certificate.certificate
├── Día 33-34: Actualizar referencias a catálogos
└── Día 35: Unificar campo UUID

Semana 6-7: TESTING
├── Día 36-38: Unit tests PACs
├── Día 39-41: Integration tests timbrado
├── Día 42-44: Integration tests descarga SAT
├── Día 45-47: Tests de regresión
└── Día 48-49: Tests en ambiente de producción

Semana 8: DOCUMENTACIÓN Y DEPLOYMENT
├── Día 50-51: Documentación técnica
├── Día 52-53: Manuales de usuario
├── Día 54-55: Scripts de migración
└── Día 56-57: Deployment a producción
```

### 9.2 Hitos Clave

| Hito | Fecha Objetivo | Entregables |
|------|----------------|-------------|
| **M1: Arquitectura Aprobada** | Semana 2 | Documentos de diseño, l10n_mx_catalogs |
| **M2: PACs Implementados** | Semana 4 | cdfi_invoice_enterprise con 3 PACs |
| **M3: SAT Sync Refactorizado** | Semana 5 | l10n_mx_sat_sync compatible |
| **M4: Tests Completos** | Semana 7 | Suite de tests >80% coverage |
| **M5: Producción** | Semana 8 | Módulos en producción |

---

## 10. RIESGOS Y MITIGACIÓN

### 10.1 Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **Incompatibilidad con Enterprise** | Media | Alto | Usar herencia de l10n_mx_edi, no reemplazo |
| **PAC APIs cambian** | Baja | Alto | Tests automatizados, monitoring |
| **Pérdida de datos en migración** | Baja | Crítico | Backup antes de migrar, scripts reversibles |
| **Certificados inválidos** | Media | Alto | Validación previa, mensajes claros |
| **Timeout en PACs** | Alta | Medio | Retry logic, failover automático |
| **Performance en descarga masiva** | Media | Medio | Procesamiento asíncrono, batch |

### 10.2 Riesgos de Negocio

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **Costo de PACs** | Media | Medio | Negociar tarifas, comparar precios |
| **Dependencia de proveedor** | Baja | Alto | Multi-PAC, failover |
| **Cambios SAT** | Alta | Alto | Monitoring activo, actualizar rápido |
| **Adopción de usuarios** | Media | Medio | Documentación clara, capacitación |

### 10.3 Plan de Contingencia

**Si falla migración**:
1. Rollback a versión anterior (backup)
2. Analizar logs de error
3. Corregir en ambiente de desarrollo
4. Re-ejecutar migración

**Si PAC no está disponible**:
1. Activar PAC de failover
2. Notificar a usuarios
3. Contactar soporte del PAC
4. Monitorear hasta restauración

**Si SAT cambia especificaciones**:
1. Analizar cambios en documentación SAT
2. Crear issue en repositorio
3. Desarrollar corrección
4. Probar en ambiente test
5. Desplegar urgentemente

---

## CONCLUSIÓN

Este plan de implementación proporciona una ruta clara para:

1. ✅ **Compatibilidad Enterprise**: Coexistencia con l10n_mx_edi sin conflictos
2. ✅ **Sistema Multi-PAC**: Arquitectura extensible con 4+ PACs
3. ✅ **Dependencias Resueltas**: Módulos desacoplados y compartibles
4. ✅ **Odoo 19 Listo**: Actualizado a últimas APIs

**Próximos Pasos Inmediatos**:
1. Aprobar este plan
2. Crear branch de desarrollo
3. Iniciar Fase 1 (l10n_mx_catalogs)
4. Configurar CI/CD para tests automáticos

**Recursos Necesarios**:
- 1 desarrollador senior (full-time, 8 semanas)
- 1 QA tester (part-time, semanas 6-7)
- Acceso a PACs de prueba (Finkok, SW, IT Admin)
- Certificados CSD/FIEL de prueba

**ROI Esperado**:
- Reducción 50% en costo de timbrado (negociación multi-PAC)
- Mejora 99.9% disponibilidad (failover automático)
- Tiempo de migración a PAC nuevo: <1 día

---

*Documento versión 1.0 - Generado el 2026-01-05*
