from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AddCollaboratorWizard(models.TransientModel):
    _name = 'saas.add.collaborator.wizard'
    _description = 'Agregar Colaborador a Proyecto'

    project_id = fields.Many2one(
        'project.project',
        string='Proyecto',
        required=True
    )
    collaborator_ids = fields.Many2many(
        'saas.collaborator',
        string='Colaboradores',
        domain=[('state', '=', 'active')],
        required=True
    )
    skill_filter_ids = fields.Many2many(
        'saas.skill',
        string='Filtrar por Skills'
    )
    send_notification = fields.Boolean(
        'Enviar Notificación',
        default=True
    )

    @api.onchange('skill_filter_ids')
    def _onchange_skill_filter(self):
        """Filter collaborators by selected skills"""
        domain = [('state', '=', 'active')]
        if self.skill_filter_ids:
            domain.append(('skill_ids', 'in', self.skill_filter_ids.ids))
        return {'domain': {'collaborator_ids': domain}}

    def action_add_collaborators(self):
        """Add selected collaborators to the project"""
        self.ensure_one()

        if not self.collaborator_ids:
            raise UserError(_('Debe seleccionar al menos un colaborador.'))

        added = []
        already_added = []

        for collaborator in self.collaborator_ids:
            result = collaborator.action_share_project(self.project_id)
            if result:
                # Check if it was already added or newly added
                if hasattr(result, 'create_date') and result.create_date:
                    # This is a simple check - newly created would have recent create_date
                    added.append(collaborator.name)
                else:
                    already_added.append(collaborator.name)

        # Send notifications if requested
        if self.send_notification and added:
            self._send_notifications(added)

        # Return confirmation
        message = []
        if added:
            message.append(_('Colaboradores agregados: %s') % ', '.join(added))
        if already_added:
            message.append(_('Ya tenían acceso: %s') % ', '.join(already_added))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Colaboradores Actualizados'),
                'message': '\n'.join(message) if message else _('No se realizaron cambios'),
                'type': 'success' if added else 'warning',
                'sticky': False,
            }
        }

    def _send_notifications(self, collaborator_names):
        """Send email notification to added collaborators"""
        template = self.env.ref(
            'saas_team.email_project_shared',
            raise_if_not_found=False
        )

        if template:
            for collaborator in self.collaborator_ids.filtered(
                lambda c: c.name in collaborator_names
            ):
                template.with_context(
                    project_name=self.project_id.name
                ).send_mail(collaborator.id, force_send=True)
