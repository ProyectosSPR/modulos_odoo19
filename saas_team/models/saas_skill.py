from odoo import models, fields, api


class SaasSkill(models.Model):
    _name = 'saas.skill'
    _description = 'Habilidad/Especialidad'
    _order = 'category, sequence, name'

    name = fields.Char('Nombre', required=True, translate=True)
    sequence = fields.Integer('Secuencia', default=10)

    category = fields.Selection([
        ('accounting', 'Contabilidad'),
        ('development', 'Desarrollo'),
        ('automation', 'Automatización'),
        ('support', 'Soporte'),
        ('training', 'Capacitación'),
        ('consulting', 'Consultoría'),
        ('design', 'Diseño'),
        ('other', 'Otro'),
    ], string='Categoría', required=True, default='other')

    description = fields.Text('Descripción')
    color = fields.Integer('Color')
    active = fields.Boolean('Activo', default=True)

    # Relaciones
    collaborator_ids = fields.Many2many(
        'saas.collaborator',
        string='Colaboradores con este Skill'
    )
    collaborator_count = fields.Integer(
        compute='_compute_collaborator_count',
        string='# Colaboradores'
    )

    product_ids = fields.Many2many(
        'product.template',
        'product_skill_rel',
        'skill_id',
        'product_id',
        string='Productos que Requieren este Skill'
    )

    @api.depends('collaborator_ids')
    def _compute_collaborator_count(self):
        for skill in self:
            skill.collaborator_count = len(skill.collaborator_ids)

    def action_view_collaborators(self):
        """Ver colaboradores con este skill"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Colaboradores: {self.name}',
            'res_model': 'saas.collaborator',
            'view_mode': 'list,form',
            'domain': [('skill_ids', 'in', self.id)],
        }
