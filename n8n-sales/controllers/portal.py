# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class N8nPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'n8n_workflow_count' in counters:
            workflow_count = request.env['n8n.workflow.instance'].sudo().search_count([
                ('partner_id', '=', partner.id)
            ])
            values['n8n_workflow_count'] = workflow_count

        return values

    # ==================
    # LISTA DE WORKFLOWS
    # ==================

    @http.route(['/my/n8n', '/my/n8n/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_n8n_workflows(self, page=1, sortby=None, filterby=None, **kw):
        """Lista de workflows N8N del cliente"""
        partner = request.env.user.partner_id
        Workflow = request.env['n8n.workflow.instance'].sudo()

        domain = [('partner_id', '=', partner.id)]

        # Filtros
        searchbar_filters = {
            'all': {'label': _('Todos'), 'domain': []},
            'pending': {'label': _('Pendientes'), 'domain': [('state', '=', 'pending')]},
            'synced': {'label': _('Sincronizados'), 'domain': [('state', '=', 'synced')]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # Ordenamiento
        searchbar_sortings = {
            'date': {'label': _('Fecha'), 'order': 'create_date desc'},
            'name': {'label': _('Nombre'), 'order': 'name'},
            'state': {'label': _('Estado'), 'order': 'state'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Conteo y paginación
        workflow_count = Workflow.search_count(domain)
        pager = portal_pager(
            url="/my/n8n",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=workflow_count,
            page=page,
            step=10
        )

        workflows = Workflow.search(
            domain,
            order=order,
            limit=10,
            offset=pager['offset']
        )

        values = {
            'workflows': workflows,
            'page_name': 'n8n_workflows',
            'pager': pager,
            'default_url': '/my/n8n',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        }

        return request.render('n8n_sales.portal_my_n8n_workflows', values)

    # ==================
    # DETALLE WORKFLOW
    # ==================

    @http.route(['/my/n8n/<int:workflow_id>'],
                type='http', auth='user', website=True)
    def portal_n8n_workflow_detail(self, workflow_id, **kw):
        """Detalle de un workflow específico"""
        partner = request.env.user.partner_id
        workflow = request.env['n8n.workflow.instance'].sudo().browse(workflow_id)

        # Verificación de seguridad
        if not workflow.exists() or workflow.partner_id.id != partner.id:
            return request.redirect('/my/n8n')

        # Obtener URL de N8N para generar API Key
        n8n_url = request.env['ir.config_parameter'].sudo().get_param('n8n_sales.n8n_url', '')
        n8n_settings_url = ''
        if n8n_url:
            import re
            base_url = n8n_url.replace('/api/v1', '').rstrip('/')
            base_url = re.sub(r':\d+', '', base_url)
            n8n_settings_url = f"{base_url}/settings/api"

        values = {
            'workflow': workflow,
            'page_name': 'n8n_workflow_detail',
            'n8n_settings_url': n8n_settings_url,
        }

        return request.render('n8n_sales.portal_n8n_workflow_detail', values)

    # ==================
    # FORMULARIO DE SINCRONIZACIÓN
    # ==================

    @http.route(['/my/n8n/<int:workflow_id>/sync'],
                type='http', auth='user', website=True, methods=['GET'])
    def portal_n8n_sync_form(self, workflow_id, **kw):
        """Formulario para sincronizar workflow"""
        partner = request.env.user.partner_id
        workflow = request.env['n8n.workflow.instance'].sudo().browse(workflow_id)

        # Verificación de seguridad
        if not workflow.exists() or workflow.partner_id.id != partner.id:
            return request.redirect('/my/n8n')

        # No permitir sincronizar si ya está sincronizado
        if workflow.state == 'synced':
            return request.redirect(f'/my/n8n/{workflow_id}')

        values = {
            'workflow': workflow,
            'page_name': 'n8n_sync_form',
            'error': kw.get('error'),
            'success': kw.get('success'),
        }

        return request.render('n8n_sales.portal_n8n_sync_form', values)

    @http.route(['/my/n8n/<int:workflow_id>/sync'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_n8n_sync_submit(self, workflow_id, **post):
        """Procesar sincronización de workflow"""
        partner = request.env.user.partner_id
        workflow = request.env['n8n.workflow.instance'].sudo().browse(workflow_id)

        # Verificación de seguridad
        if not workflow.exists() or workflow.partner_id.id != partner.id:
            return request.redirect('/my/n8n')

        # Validar campos requeridos
        n8n_api_key = post.get('n8n_api_key', '').strip()
        odoo_url = post.get('odoo_url', '').strip()
        odoo_db = post.get('odoo_db', '').strip()
        odoo_user = post.get('odoo_user', '').strip()
        odoo_password = post.get('odoo_password', '').strip()

        if not all([n8n_api_key, odoo_url, odoo_db, odoo_user, odoo_password]):
            return request.redirect(f'/my/n8n/{workflow_id}/sync?error=missing_fields')

        try:
            # Ejecutar sincronización
            self._sync_workflow(workflow, n8n_api_key, odoo_url, odoo_db, odoo_user, odoo_password)
            return request.redirect(f'/my/n8n/{workflow_id}?success=synced')

        except Exception as e:
            _logger.error(f"Error sincronizando workflow {workflow_id}: {e}")
            return request.redirect(f'/my/n8n/{workflow_id}/sync?error={str(e)[:100]}')

    def _sync_workflow(self, workflow, n8n_api_key, odoo_url, odoo_db, odoo_user, odoo_password):
        """Lógica de sincronización del workflow"""
        try:
            template_data = json.loads(workflow.template_json or '{}')
        except json.JSONDecodeError:
            raise ValidationError("El JSON de la plantilla está corrupto.")

        n8n_master_url = request.env['ir.config_parameter'].sudo().get_param('n8n_sales.n8n_url')
        if not n8n_master_url:
            raise ValidationError("N8N no está configurado en el sistema.")

        headers = {
            "X-N8N-API-KEY": n8n_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # PASO 1: Crear workflow base
        _logger.info(f"Portal Sync - Paso 1: Creando workflow base para {workflow.id}")
        clean_payload = {
            'name': template_data.get('name', 'Workflow Sincronizado'),
            'nodes': template_data.get('nodes', []),
            'connections': template_data.get('connections', {}),
            'settings': template_data.get('settings', {}),
        }
        for node in clean_payload.get('nodes', []):
            node.pop('webhookId', None)

        create_url = f"{n8n_master_url}/api/v1/workflows"
        response_create = requests.post(create_url, headers=headers, json=clean_payload, timeout=20)
        response_create.raise_for_status()
        new_workflow_info = response_create.json()
        new_workflow_id = new_workflow_info.get('id')

        if not new_workflow_id:
            raise ValidationError("N8N no devolvió un ID de workflow.")

        _logger.info(f"Portal Sync - Workflow creado con ID: {new_workflow_id}")

        # PASO 2: Actualizar nodo configuracion_cliente
        _logger.info(f"Portal Sync - Paso 2: Actualizando configuracion_cliente")

        get_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}"
        response_get = requests.get(get_url, headers=headers, timeout=15)
        response_get.raise_for_status()
        workflow_to_update = response_get.json()

        odoo_creds = {
            'url': odoo_url.rstrip('/'),
            'database': odoo_db,
            'username': odoo_user,
            'password': odoo_password,
            'source': 'n8n_sales_portal_sync'
        }

        node_found = False
        for node in workflow_to_update.get('nodes', []):
            if node.get('name', '').strip().lower() == 'configuracion_cliente':
                if 'jsonOutput' in node.get('parameters', {}):
                    node['parameters']['jsonOutput'] = json.dumps(odoo_creds, indent=2)
                    node_found = True
                    break

        if not node_found:
            _logger.warning(f"Nodo configuracion_cliente no encontrado en workflow {new_workflow_id}")

        clean_update_payload = {
            'name': workflow_to_update.get('name'),
            'nodes': workflow_to_update.get('nodes'),
            'connections': workflow_to_update.get('connections'),
            'settings': workflow_to_update.get('settings'),
        }

        update_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}"
        response_update = requests.put(update_url, headers=headers, json=clean_update_payload, timeout=20)
        response_update.raise_for_status()

        _logger.info(f"Portal Sync - Workflow actualizado")

        # PASO 3: Activar y guardar
        workflow.write({
            'n8n_instance_id': new_workflow_id,
            'state': 'synced',
        })

        activate_url = f"{n8n_master_url}/api/v1/workflows/{new_workflow_id}/activate"
        requests.post(activate_url, headers=headers, timeout=10)

        _logger.info(f"Portal Sync - Workflow {workflow.id} sincronizado exitosamente")

    # ==================
    # EXTENSIONES
    # ==================

    @http.route(['/my/n8n/<int:workflow_id>/apply-extension'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_apply_extension(self, workflow_id, **post):
        """Aplicar extensión a un workflow"""
        partner = request.env.user.partner_id
        workflow = request.env['n8n.workflow.instance'].sudo().browse(workflow_id)

        # Verificación de seguridad
        if not workflow.exists() or workflow.partner_id.id != partner.id:
            return request.redirect('/my/n8n')

        if not workflow.is_extension:
            return request.redirect(f'/my/n8n/{workflow_id}?error=not_extension')

        try:
            if workflow.merge_strategy == 'full_replace':
                workflow.action_apply_extension_full_replace()
            else:
                workflow.action_apply_extension_manual_merge()

            return request.redirect(f'/my/n8n/{workflow_id}?success=extension_applied')

        except Exception as e:
            _logger.error(f"Error aplicando extensión {workflow_id}: {e}")
            return request.redirect(f'/my/n8n/{workflow_id}?error={str(e)[:100]}')
