from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Portal visibility settings
    portal_show_instances = fields.Boolean(
        'Mostrar Instancias en Portal',
        default=True,
        help='Mostrar las instancias K8s vinculadas en el portal del cliente'
    )
    portal_show_appointments = fields.Boolean(
        'Mostrar Citas en Portal',
        default=True
    )
    portal_show_projects = fields.Boolean(
        'Mostrar Proyectos en Portal',
        default=True
    )

    def _get_portal_instances(self):
        """Get instances visible in portal for this subscription"""
        self.ensure_one()
        if not self.portal_show_instances:
            return self.env['k8s.instance']
        return self.k8s_instance_ids.filtered(
            lambda i: i.state in ('running', 'stopped')
        )

    def _get_portal_projects(self):
        """Get projects visible in portal for this subscription"""
        self.ensure_one()
        if not self.portal_show_projects:
            return self.env['project.project']
        return self.project_ids


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_all_subscriptions(self):
        """Get all active subscriptions for portal display"""
        self.ensure_one()
        return self.env['sale.order'].search([
            ('partner_id', '=', self.id),
            ('is_subscription', '=', True),
            ('subscription_state', 'in', ('3_progress', '4_paused')),
        ])

    def _get_all_k8s_instances(self):
        """Get all K8s instances for this partner"""
        self.ensure_one()
        return self.env['k8s.instance'].search([
            ('partner_id', '=', self.id),
            ('state', 'in', ('running', 'stopped')),
        ])

    def _get_upcoming_appointments(self):
        """Get upcoming appointments for this partner"""
        self.ensure_one()
        return self.env['calendar.event'].search([
            ('partner_ids', 'in', self.id),
            ('start', '>=', fields.Datetime.now()),
        ], order='start asc', limit=5)

    def _get_active_projects(self):
        """Get active projects where this partner is involved"""
        self.ensure_one()
        # Projects where partner is customer or collaborator
        projects = self.env['project.project'].search([
            '|',
            ('partner_id', '=', self.id),
            ('collaborator_ids.partner_id', '=', self.id),
        ])
        return projects
