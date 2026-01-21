# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import json
import requests
import logging

_logger = logging.getLogger(__name__)


class N8nSyncWizard(models.TransientModel):
    _name = 'n8n.sync.wizard'
    _description = 'Asistente de Sincronización de Workflows N8N'

    workflow_instance_id = fields.Many2one('n8n.workflow.instance', readonly=True)
    n8n_api_key = fields.Char(string="Tu API Key de N8N", required=True)

    # Campos de conexión al Odoo del cliente (OBLIGATORIOS)
    odoo_url = fields.Char(
        string="URL de tu Odoo",
        required=True,
        help="URL completa de tu instancia de Odoo (ej: https://miempresa.odoo.com)"
    )
    odoo_db = fields.Char(
        string="Base de Datos",
        required=True,
        help="Nombre de la base de datos de tu Odoo"
    )
    odoo_user = fields.Char(
        string="Usuario",
        required=True,
        help="Email o login del usuario de tu Odoo"
    )
    odoo_password = fields.Char(
        string="Contraseña / API Key",
        required=True,
        help="Contraseña o API Key del usuario"
    )

    @api.constrains('odoo_url', 'odoo_db', 'odoo_user', 'odoo_password')
    def _check_odoo_fields(self):
        for record in self:
            if not all([record.odoo_url, record.odoo_db, record.odoo_user, record.odoo_password]):
                raise ValidationError("Todos los campos de conexión a tu Odoo son obligatorios.")

    def action_synchronize(self):
        self.ensure_one()
        workflow = self.workflow_instance_id
        
        try:
            template_data = json.loads(workflow.template_json or '{}')
        except json.JSONDecodeError:
            raise UserError("El JSON de la plantilla base está corrupto.")

        n8n_master_url = self.env['ir.config_parameter'].sudo().get_param('n8n_sales.n8n_url')
        headers = {
            "X-N8N-API-KEY": self.n8n_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # --- PASO 1: Crear el workflow como una copia limpia de la plantilla ---
        _logger.info("Paso 1: Creando workflow base en N8N...")
        clean_payload = {
            'name': template_data.get('name', 'Workflow Sincronizado'),
            'nodes': template_data.get('nodes', []),
            'connections': template_data.get('connections', {}),
            'settings': template_data.get('settings', {}),
        }
        for node in clean_payload.get('nodes', []):
            node.pop('webhookId', None)

        create_url = f"{n8n_master_url}/api/v1/workflows"
        try:
            response_create = requests.post(create_url, headers=headers, json=clean_payload, timeout=20)
            response_create.raise_for_status()
            new_workflow_info = response_create.json()
            new_workflow_id = new_workflow_info.get('id')
            if not new_workflow_id:
                raise UserError("N8N creó el workflow pero no devolvió un ID.")
            _logger.info(f"Workflow base creado con ID: {new_workflow_id}")

        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response else str(e)
            raise UserError(f"Error en el PASO 1 (Crear Workflow): {error_details}")

        # --- PASO 2: Actualizar el workflow recién creado con los datos del cliente ---
        _logger.info("Paso 2: Actualizando nodo 'configuracion_cliente'...")
        
        get_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}"
        response_get = requests.get(get_url, headers=headers, timeout=15)
        response_get.raise_for_status()
        workflow_to_update = response_get.json()

        # Construimos el diccionario de credenciales con los datos del Odoo del cliente
        odoo_creds = {
            'url': self.odoo_url.rstrip('/'),
            'database': self.odoo_db,
            'username': self.odoo_user,
            'password': self.odoo_password,
            'source': 'n8n_sales_portal_sync'
        }

        node_found = False
        for node in workflow_to_update.get('nodes', []):
            if node.get('name', '').strip().lower() == 'configuracion_cliente':
                if 'jsonOutput' in node['parameters']:
                    node['parameters']['jsonOutput'] = json.dumps(odoo_creds, indent=2)
                    node_found = True
                    break
        
        if not node_found:
            raise UserError("Se creó el workflow, pero no se pudo encontrar el nodo 'configuracion_cliente' para actualizarlo.")

        clean_update_payload = {
            'name': workflow_to_update.get('name'),
            'nodes': workflow_to_update.get('nodes'),
            'connections': workflow_to_update.get('connections'),
            'settings': workflow_to_update.get('settings'),
        }

        update_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}"
        try:
            response_update = requests.put(update_url, headers=headers, json=clean_update_payload, timeout=20)
            response_update.raise_for_status()
            _logger.info(f"Nodo 'configuracion_cliente' actualizado exitosamente en workflow ID: {new_workflow_id}")

        except requests.exceptions.RequestException as e:
            error_details = e.response.text if hasattr(e, 'response') and e.response else str(e)
            raise UserError(f"Error en el PASO 2 (Actualizar Workflow): {error_details}")

        # --- PASO 3: Guardar y activar ---
        workflow.write({
            'n8n_instance_id': new_workflow_id,
            'state': 'synced',
        })
        activate_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}/activate"
        requests.post(activate_url, headers=headers, timeout=10)

        return {'type': 'ir.actions.act_window_close'}