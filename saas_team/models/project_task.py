from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Enlace a colaborador asignado (además de user_ids)
    collaborator_ids = fields.Many2many(
        'saas.collaborator',
        string='Colaboradores Asignados',
        compute='_compute_collaborator_ids',
        store=True
    )

    @api.depends('user_ids')
    def _compute_collaborator_ids(self):
        """Calcular colaboradores basándose en los usuarios asignados"""
        Collaborator = self.env['saas.collaborator']
        for task in self:
            if task.user_ids:
                collaborators = Collaborator.search([
                    ('user_id', 'in', task.user_ids.ids)
                ])
                task.collaborator_ids = collaborators
            else:
                task.collaborator_ids = False


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Colaboradores del proyecto (via project.collaborator nativo)
    saas_collaborator_ids = fields.Many2many(
        'saas.collaborator',
        string='Colaboradores SaaS',
        compute='_compute_saas_collaborators',
        store=True
    )
    saas_collaborator_count = fields.Integer(
        compute='_compute_saas_collaborators',
        string='# Colaboradores'
    )

    # Skills requeridos para el proyecto
    required_skill_ids = fields.Many2many(
        'saas.skill',
        string='Skills Requeridos'
    )

    @api.depends('collaborator_ids', 'collaborator_ids.partner_id')
    def _compute_saas_collaborators(self):
        """Mapear project.collaborator a saas.collaborator"""
        SaasCollaborator = self.env['saas.collaborator']
        for project in self:
            partner_ids = project.collaborator_ids.mapped('partner_id').ids
            if partner_ids:
                saas_collabs = SaasCollaborator.search([
                    ('partner_id', 'in', partner_ids)
                ])
                project.saas_collaborator_ids = saas_collabs
                project.saas_collaborator_count = len(saas_collabs)
            else:
                project.saas_collaborator_ids = False
                project.saas_collaborator_count = 0

    def action_add_collaborator(self):
        """Wizard para agregar colaborador al proyecto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Agregar Colaborador',
            'res_model': 'saas.add.collaborator.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
            },
        }

    def action_view_saas_collaborators(self):
        """Ver colaboradores SaaS del proyecto"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Colaboradores',
            'res_model': 'saas.collaborator',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.saas_collaborator_ids.ids)],
        }
