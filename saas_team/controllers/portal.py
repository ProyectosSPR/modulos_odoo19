from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class CollaboratorPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        # Check if current user is a collaborator
        collaborator = request.env['saas.collaborator'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

        if collaborator:
            values['collaborator'] = collaborator

            if 'collaborator_project_count' in counters:
                values['collaborator_project_count'] = len(collaborator.project_ids)

        return values

    @http.route(['/my/collaborator/projects'], type='http', auth='user', website=True)
    def portal_collaborator_projects(self, **kw):
        collaborator = request.env['saas.collaborator'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

        if not collaborator:
            return request.redirect('/my')

        values = {
            'collaborator': collaborator,
            'projects': collaborator.project_ids,
            'page_name': 'collaborator_projects',
        }

        return request.render('saas_team.portal_my_collaborator_projects', values)

    @http.route(['/my/collaborator/balance'], type='http', auth='user', website=True)
    def portal_collaborator_balance(self, **kw):
        collaborator = request.env['saas.collaborator'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

        if not collaborator:
            return request.redirect('/my')

        payments = request.env['saas.collaborator.payment'].sudo().search([
            ('collaborator_id', '=', collaborator.id)
        ], order='date desc')

        values = {
            'collaborator': collaborator,
            'payments': payments,
            'page_name': 'collaborator_balance',
        }

        return request.render('saas_team.portal_my_collaborator_balance', values)
