import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CollaboratorApplication(http.Controller):

    @http.route(['/collaborator/apply'], type='http', auth='public', website=True)
    def collaborator_apply_form(self, **kw):
        """Display the collaborator application form"""
        skills = request.env['saas.skill'].sudo().search([('active', '=', True)])

        values = {
            'skills': skills,
        }

        return request.render('saas_team.collaborator_apply_form', values)

    @http.route(['/collaborator/apply/submit'], type='http', auth='public', website=True, methods=['POST'])
    def collaborator_apply_submit(self, **post):
        """Process the collaborator application"""
        try:
            # Create or find partner
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('email', '=', post.get('email'))], limit=1)

            if not partner:
                partner_vals = {
                    'name': post.get('name'),
                    'email': post.get('email'),
                    'phone': post.get('phone'),
                    'website': post.get('linkedin'),
                    'is_company': False,
                }
                partner = Partner.create(partner_vals)

            # Prepare skill_ids
            skill_ids = []
            if post.get('skill_ids'):
                if isinstance(post.get('skill_ids'), list):
                    skill_ids = [(6, 0, [int(s) for s in post.get('skill_ids')])]
                else:
                    skill_ids = [(6, 0, [int(post.get('skill_ids'))])]

            # Create collaborator
            Collaborator = request.env['saas.collaborator'].sudo()

            # Check if already exists
            existing = Collaborator.search([('partner_id', '=', partner.id)], limit=1)
            if existing:
                _logger.info(f"Collaborator already exists for partner {partner.name}")
                return request.redirect('/collaborator/apply/success')

            collab_vals = {
                'partner_id': partner.id,
                'skill_ids': skill_ids,
                'skill_level': post.get('skill_level', 'mid'),
                'availability': post.get('availability', 'hours'),
                'hours_per_week': float(post.get('hours_per_week', 20)),
                'rate_type': 'hourly',
                'rate_amount': float(post.get('rate_amount', 0)) if post.get('rate_amount') else 0,
                'application_source': post.get('application_source', 'website'),
                'application_notes': post.get('application_notes'),
                'state': 'candidate',
            }

            collaborator = Collaborator.create(collab_vals)

            # Handle CV upload
            if post.get('cv_file'):
                cv_file = post.get('cv_file')
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': cv_file.filename,
                    'datas': base64.b64encode(cv_file.read()),
                    'res_model': 'saas.collaborator',
                    'res_id': collaborator.id,
                })
                collaborator.write({'cv_attachment_ids': [(4, attachment.id)]})

            _logger.info(f"New collaborator application created: {collaborator.name}")

            # Send notification to managers
            self._notify_new_application(collaborator)

            return request.redirect('/collaborator/apply/success')

        except Exception as e:
            _logger.error(f"Error processing collaborator application: {e}")
            return request.redirect('/collaborator/apply?error=1')

    @http.route(['/collaborator/apply/success'], type='http', auth='public', website=True)
    def collaborator_apply_success(self, **kw):
        """Show success page after application"""
        return request.render('saas_team.collaborator_apply_success', {})

    def _notify_new_application(self, collaborator):
        """Send notification to team managers about new application"""
        try:
            # Find users in the manager group
            manager_group = request.env.ref('saas_team.group_saas_team_manager', raise_if_not_found=False)
            if manager_group:
                managers = manager_group.sudo().users
                if managers:
                    # Post message on collaborator
                    collaborator.message_post(
                        body=f"Nueva aplicación recibida de {collaborator.name}",
                        subject="Nueva Aplicación de Colaborador",
                        partner_ids=managers.mapped('partner_id').ids,
                        message_type='notification',
                    )
        except Exception as e:
            _logger.warning(f"Could not send notification for new application: {e}")
