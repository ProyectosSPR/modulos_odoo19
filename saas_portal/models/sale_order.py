from odoo import models, fields, api
from datetime import datetime, timedelta


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

    # ==================
    # DASHBOARD METRICS
    # ==================

    def _get_k8s_metrics_summary(self):
        """Get summary of K8s instances metrics"""
        self.ensure_one()
        instances = self._get_all_k8s_instances()

        running = instances.filtered(lambda i: i.state == 'running')
        stopped = instances.filtered(lambda i: i.state == 'stopped')

        # Calculate totals from plans
        total_cpu = sum(i.plan_id.cpu_limit for i in instances if i.plan_id)
        total_memory = sum(i.plan_id.memory_limit for i in instances if i.plan_id)
        total_storage = sum(i.plan_id.storage_size for i in instances if i.plan_id)

        return {
            'total': len(instances),
            'running': len(running),
            'stopped': len(stopped),
            'total_cpu': total_cpu,
            'total_memory': total_memory,
            'total_storage': total_storage,
            'instances': instances,
        }

    def _get_n8n_workflows_summary(self):
        """Get summary of N8N workflows"""
        self.ensure_one()

        # Check if n8n_sales module is installed
        if 'n8n.workflow.instance' not in self.env:
            return {
                'available': False,
                'total': 0,
                'active': 0,
                'inactive': 0,
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0,
                'success_rate': 0,
                'workflows': self.env['n8n.workflow.instance'] if 'n8n.workflow.instance' in self.env else [],
            }

        workflows = self.env['n8n.workflow.instance'].search([
            ('partner_id', '=', self.id),
            ('state', '=', 'synced'),
        ])

        active = workflows.filtered(lambda w: w.is_active)
        total_exec = sum(workflows.mapped('total_executions'))
        success_exec = sum(workflows.mapped('successful_executions'))
        failed_exec = sum(workflows.mapped('failed_executions'))
        success_rate = (success_exec / total_exec * 100) if total_exec > 0 else 100

        return {
            'available': True,
            'total': len(workflows),
            'active': len(active),
            'inactive': len(workflows) - len(active),
            'total_executions': total_exec,
            'successful_executions': success_exec,
            'failed_executions': failed_exec,
            'success_rate': round(success_rate, 1),
            'workflows': workflows,
        }

    def _get_billing_summary(self):
        """Get billing and invoice summary"""
        self.ensure_one()

        # Pending invoices
        pending_invoices = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('state', '=', 'posted'),
        ])

        # Paid invoices this month
        first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        paid_this_month = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('payment_state', '=', 'paid'),
            ('invoice_date', '>=', first_day.date()),
        ])

        # Active subscriptions
        subscriptions = self._get_all_subscriptions()

        # Next payment date
        next_payments = subscriptions.filtered(
            lambda s: s.next_invoice_date
        ).sorted('next_invoice_date')

        next_payment_date = next_payments[0].next_invoice_date if next_payments else None

        # Monthly recurring
        monthly_recurring = sum(subscriptions.mapped('recurring_monthly'))

        return {
            'pending_invoices': pending_invoices,
            'pending_amount': sum(pending_invoices.mapped('amount_residual')),
            'pending_count': len(pending_invoices),
            'paid_this_month': sum(paid_this_month.mapped('amount_total')),
            'paid_count': len(paid_this_month),
            'next_payment_date': next_payment_date,
            'monthly_recurring': monthly_recurring,
            'active_subscriptions': len(subscriptions),
            'currency': self.env.company.currency_id,
        }

    def _get_recent_notifications(self):
        """Get recent notifications/alerts for dashboard"""
        self.ensure_one()
        notifications = []

        # Check for pending invoices
        pending = self.env['account.move'].search([
            ('partner_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('state', '=', 'posted'),
        ], limit=3)

        for inv in pending:
            notifications.append({
                'type': 'warning',
                'icon': 'fa-exclamation-triangle',
                'title': 'Factura Pendiente',
                'message': f'{inv.name} - {inv.amount_residual} {inv.currency_id.symbol}',
                'link': f'/my/invoices/{inv.id}',
                'date': inv.invoice_date,
            })

        # Check for stopped instances
        stopped_instances = self.env['k8s.instance'].search([
            ('partner_id', '=', self.id),
            ('state', '=', 'stopped'),
        ])

        for inst in stopped_instances:
            notifications.append({
                'type': 'info',
                'icon': 'fa-pause-circle',
                'title': 'Instancia Detenida',
                'message': f'{inst.name} está actualmente detenida',
                'link': f'/my/instance/{inst.id}',
                'date': inst.write_date,
            })

        # Check for instances with errors
        error_instances = self.env['k8s.instance'].search([
            ('partner_id', '=', self.id),
            ('state', '=', 'error'),
        ])

        for inst in error_instances:
            notifications.append({
                'type': 'danger',
                'icon': 'fa-times-circle',
                'title': 'Instancia con Error',
                'message': f'{inst.name} tiene un problema',
                'link': f'/my/instance/{inst.id}',
                'date': inst.write_date,
            })

        # Check for failed N8N workflows
        if 'n8n.workflow.instance' in self.env:
            failed_workflows = self.env['n8n.workflow.instance'].search([
                ('partner_id', '=', self.id),
                ('last_execution_status', '=', 'failed'),
            ], limit=3)

            for wf in failed_workflows:
                notifications.append({
                    'type': 'warning',
                    'icon': 'fa-exclamation',
                    'title': 'Workflow con Fallo',
                    'message': f'{wf.custom_name or wf.product_id.name} falló',
                    'link': f'/my/n8n/{wf.id}',
                    'date': wf.last_execution_date,
                })

        # Check for upcoming appointments
        tomorrow = datetime.now() + timedelta(days=1)
        upcoming = self.env['calendar.event'].search([
            ('partner_ids', 'in', self.id),
            ('start', '>=', fields.Datetime.now()),
            ('start', '<=', tomorrow),
        ], limit=2)

        for apt in upcoming:
            notifications.append({
                'type': 'success',
                'icon': 'fa-calendar-check-o',
                'title': 'Cita Próxima',
                'message': apt.name,
                'link': '/my/appointments',
                'date': apt.start,
            })

        # Sort by date
        notifications.sort(key=lambda x: x['date'] or datetime.min, reverse=True)

        return notifications[:10]

    def _get_tasks_summary(self):
        """Get tasks summary for projects"""
        self.ensure_one()

        projects = self._get_active_projects()
        if not projects:
            return {
                'total': 0,
                'open': 0,
                'in_progress': 0,
                'done': 0,
            }

        tasks = self.env['project.task'].search([
            ('project_id', 'in', projects.ids),
        ])

        done = tasks.filtered(lambda t: t.stage_id.fold)
        open_tasks = tasks.filtered(lambda t: not t.stage_id.fold)

        return {
            'total': len(tasks),
            'open': len(open_tasks),
            'done': len(done),
            'recent': tasks.sorted('write_date', reverse=True)[:5],
        }
