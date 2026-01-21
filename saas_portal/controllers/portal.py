from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import json


class SaaSPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'subscription_count' in counters:
            subscriptions = partner._get_all_subscriptions()
            values['subscription_count'] = len(subscriptions)

        if 'instance_count' in counters:
            instances = partner._get_all_k8s_instances()
            values['instance_count'] = len(instances)

        if 'appointment_count' in counters:
            appointments = partner._get_upcoming_appointments()
            values['appointment_count'] = len(appointments)

        if 'project_count' in counters:
            projects = partner._get_active_projects()
            values['project_count'] = len(projects)

        # Notifications count for badge
        if 'notification_count' in counters:
            notifications = partner._get_recent_notifications()
            values['notification_count'] = len([n for n in notifications if n['type'] in ('danger', 'warning')])

        return values

    # ==================
    # DASHBOARD
    # ==================

    @http.route(['/my/saas'], type='http', auth='user', website=True)
    def portal_saas_dashboard(self, **kw):
        """SaaS Dashboard with overview of all services"""
        partner = request.env.user.partner_id

        # Basic data
        subscriptions = partner._get_all_subscriptions()
        instances = partner._get_all_k8s_instances()
        appointments = partner._get_upcoming_appointments()
        projects = partner._get_active_projects()

        # Enhanced metrics
        k8s_metrics = partner._get_k8s_metrics_summary()
        n8n_summary = partner._get_n8n_workflows_summary()
        billing_summary = partner._get_billing_summary()
        notifications = partner._get_recent_notifications()
        tasks_summary = partner._get_tasks_summary()

        values = {
            'subscriptions': subscriptions,
            'instances': instances,
            'appointments': appointments,
            'projects': projects,
            'page_name': 'saas_dashboard',
            # Enhanced metrics
            'k8s_metrics': k8s_metrics,
            'n8n_summary': n8n_summary,
            'billing': billing_summary,
            'notifications': notifications,
            'tasks': tasks_summary,
        }

        return request.render('saas_portal.portal_saas_dashboard', values)

    @http.route(['/my/saas/api/metrics'], type='json', auth='user')
    def portal_saas_api_metrics(self, **kw):
        """JSON API endpoint for dashboard metrics (for AJAX refresh)"""
        partner = request.env.user.partner_id

        k8s_metrics = partner._get_k8s_metrics_summary()
        n8n_summary = partner._get_n8n_workflows_summary()
        billing_summary = partner._get_billing_summary()

        return {
            'k8s': {
                'total': k8s_metrics['total'],
                'running': k8s_metrics['running'],
                'stopped': k8s_metrics['stopped'],
                'total_cpu': k8s_metrics['total_cpu'],
                'total_memory': k8s_metrics['total_memory'],
            },
            'n8n': {
                'total': n8n_summary['total'],
                'active': n8n_summary['active'],
                'total_executions': n8n_summary['total_executions'],
                'success_rate': n8n_summary['success_rate'],
            },
            'billing': {
                'pending_amount': billing_summary['pending_amount'],
                'pending_count': billing_summary['pending_count'],
                'monthly_recurring': billing_summary['monthly_recurring'],
            }
        }

    @http.route(['/my/saas/notifications'], type='http', auth='user', website=True)
    def portal_saas_notifications(self, **kw):
        """View all notifications"""
        partner = request.env.user.partner_id
        notifications = partner._get_recent_notifications()

        values = {
            'notifications': notifications,
            'page_name': 'saas_notifications',
        }

        return request.render('saas_portal.portal_saas_notifications', values)

    # ==================
    # SUBSCRIPTIONS
    # ==================

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_subscriptions(self, page=1, sortby=None, **kw):
        """List all subscriptions"""
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order']

        domain = [
            ('partner_id', '=', partner.id),
            ('is_subscription', '=', True),
        ]

        # Sorting
        searchbar_sortings = {
            'date': {'label': _('Fecha'), 'order': 'date_order desc'},
            'name': {'label': _('Referencia'), 'order': 'name'},
            'stage': {'label': _('Estado'), 'order': 'subscription_state'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Count for pager
        subscription_count = SaleOrder.search_count(domain)

        # Pager
        pager = portal_pager(
            url="/my/subscriptions",
            url_args={'sortby': sortby},
            total=subscription_count,
            page=page,
            step=10
        )

        # Content
        subscriptions = SaleOrder.search(
            domain,
            order=order,
            limit=10,
            offset=pager['offset']
        )

        values = {
            'subscriptions': subscriptions,
            'page_name': 'subscriptions',
            'pager': pager,
            'default_url': '/my/subscriptions',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        }

        return request.render('saas_portal.portal_my_subscriptions', values)

    @http.route(['/my/subscription/<int:subscription_id>'],
                type='http', auth='user', website=True)
    def portal_subscription_detail(self, subscription_id, **kw):
        """Subscription detail page"""
        subscription = request.env['sale.order'].sudo().browse(subscription_id)

        # Security check
        if subscription.partner_id != request.env.user.partner_id:
            return request.redirect('/my')

        # Get related data
        instances = subscription._get_portal_instances()
        projects = subscription._get_portal_projects()

        values = {
            'subscription': subscription,
            'instances': instances,
            'projects': projects,
            'page_name': 'subscription_detail',
        }

        return request.render('saas_portal.portal_subscription_detail', values)

    # ==================
    # INSTANCES
    # ==================

    @http.route(['/my/instances', '/my/instances/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_instances(self, page=1, **kw):
        """List all K8s instances"""
        partner = request.env.user.partner_id
        Instance = request.env['k8s.instance']

        domain = [
            ('partner_id', '=', partner.id),
            ('state', 'in', ('running', 'stopped')),
        ]

        instance_count = Instance.sudo().search_count(domain)

        pager = portal_pager(
            url="/my/instances",
            total=instance_count,
            page=page,
            step=10
        )

        instances = Instance.sudo().search(
            domain,
            limit=10,
            offset=pager['offset']
        )

        values = {
            'instances': instances,
            'page_name': 'instances',
            'pager': pager,
        }

        return request.render('saas_portal.portal_my_instances', values)

    @http.route(['/my/instance/<int:instance_id>'],
                type='http', auth='user', website=True)
    def portal_instance_detail(self, instance_id, **kw):
        """Instance detail page"""
        instance = request.env['k8s.instance'].sudo().browse(instance_id)

        # Security check
        if instance.partner_id != request.env.user.partner_id:
            return request.redirect('/my')

        values = {
            'instance': instance,
            'page_name': 'instance_detail',
        }

        return request.render('saas_portal.portal_instance_detail', values)

    @http.route(['/my/instance/<int:instance_id>/open'],
                type='http', auth='user', website=True)
    def portal_instance_open(self, instance_id, **kw):
        """Redirect to instance URL"""
        instance = request.env['k8s.instance'].sudo().browse(instance_id)

        # Security check
        if instance.partner_id != request.env.user.partner_id:
            return request.redirect('/my')

        if instance.url and instance.state == 'running':
            return request.redirect(instance.url)
        else:
            return request.redirect('/my/instances')
