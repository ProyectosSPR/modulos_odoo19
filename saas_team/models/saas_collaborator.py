import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaasCollaborator(models.Model):
    _name = 'saas.collaborator'
    _description = 'Colaborador/Freelancer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, name'

    # === INFORMACIÓN BÁSICA ===
    name = fields.Char(
        'Nombre',
        compute='_compute_name',
        store=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Portal',
        compute='_compute_user_id',
        store=True
    )
    image_128 = fields.Image(related='partner_id.image_128', readonly=True)
    email = fields.Char(related='partner_id.email', readonly=True)
    phone = fields.Char(related='partner_id.phone', readonly=True)

    # === ESTADO ===
    state = fields.Selection([
        ('candidate', 'Candidato'),
        ('interview', 'En Entrevista'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
        ('inactive', 'Inactivo'),
    ], string='Estado', default='candidate', tracking=True, required=True)

    # === SKILLS ===
    skill_ids = fields.Many2many(
        'saas.skill',
        string='Habilidades',
        tracking=True
    )
    skill_level = fields.Selection([
        ('junior', 'Junior'),
        ('mid', 'Mid-Level'),
        ('senior', 'Senior'),
        ('expert', 'Experto'),
    ], string='Nivel', default='mid')

    # === DISPONIBILIDAD ===
    availability = fields.Selection([
        ('full', 'Tiempo Completo'),
        ('part', 'Medio Tiempo'),
        ('project', 'Por Proyecto'),
        ('hours', 'Por Horas'),
    ], string='Disponibilidad', default='hours')

    hours_per_week = fields.Float(
        'Horas Disponibles/Semana',
        default=20.0
    )
    appointment_type_ids = fields.Many2many(
        'appointment.type',
        string='Tipos de Cita que Atiende'
    )

    # === COMPENSACIÓN ===
    rate_type = fields.Selection([
        ('hourly', 'Por Hora'),
        ('project', 'Por Proyecto'),
        ('monthly', 'Mensual'),
    ], string='Tipo de Tarifa', default='hourly')

    rate_amount = fields.Float('Tarifa')
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id
    )

    # === BALANCE Y PAGOS ===
    balance = fields.Monetary(
        string='Saldo Pendiente',
        compute='_compute_balance',
        currency_field='currency_id',
        store=True
    )
    total_earned = fields.Monetary(
        string='Total Ganado',
        compute='_compute_balance',
        currency_field='currency_id',
        store=True
    )
    total_paid = fields.Monetary(
        string='Total Pagado',
        compute='_compute_balance',
        currency_field='currency_id',
        store=True
    )
    payment_ids = fields.One2many(
        'saas.collaborator.payment',
        'collaborator_id',
        string='Pagos'
    )

    # === TRABAJO ===
    project_ids = fields.Many2many(
        'project.project',
        string='Proyectos Asignados',
        compute='_compute_projects',
        store=True
    )
    project_count = fields.Integer(
        compute='_compute_project_stats',
        string='# Proyectos'
    )
    task_count = fields.Integer(
        compute='_compute_project_stats',
        string='# Tareas'
    )
    hours_worked = fields.Float(
        compute='_compute_hours_worked',
        string='Horas Trabajadas'
    )
    hours_this_week = fields.Float(
        compute='_compute_hours_this_week',
        string='Horas Esta Semana'
    )

    # === APLICACIÓN ===
    application_date = fields.Date(
        'Fecha de Aplicación',
        default=fields.Date.today
    )
    hire_date = fields.Date('Fecha de Contratación')
    termination_date = fields.Date('Fecha de Baja')

    application_source = fields.Selection([
        ('website', 'Sitio Web'),
        ('workana', 'Workana'),
        ('freelancer', 'Freelancer.com'),
        ('upwork', 'Upwork'),
        ('referral', 'Referido'),
        ('linkedin', 'LinkedIn'),
        ('other', 'Otro'),
    ], string='Fuente de Aplicación')

    application_notes = fields.Text('Notas de Aplicación')
    cv_attachment_ids = fields.Many2many(
        'ir.attachment',
        string='CV/Portfolio'
    )

    # === MÉTRICAS ===
    rating = fields.Float('Calificación', default=5.0)

    @api.depends('partner_id')
    def _compute_name(self):
        for collab in self:
            collab.name = collab.partner_id.name if collab.partner_id else ''

    @api.depends('partner_id.user_ids')
    def _compute_user_id(self):
        for collab in self:
            portal_users = collab.partner_id.user_ids.filtered(lambda u: u.share)
            collab.user_id = portal_users[:1] if portal_users else False

    @api.depends('payment_ids', 'payment_ids.state', 'payment_ids.amount',
                 'hours_worked', 'rate_amount')
    def _compute_balance(self):
        for collab in self:
            # Total ganado = horas × tarifa
            collab.total_earned = collab.hours_worked * collab.rate_amount

            # Total pagado
            paid_payments = collab.payment_ids.filtered(
                lambda p: p.state == 'paid'
            )
            collab.total_paid = sum(paid_payments.mapped('amount'))

            # Balance = ganado - pagado
            collab.balance = collab.total_earned - collab.total_paid

    @api.depends('user_id')
    def _compute_projects(self):
        """Obtener proyectos donde es colaborador vía project.collaborator"""
        ProjectCollab = self.env['project.collaborator']
        for collab in self:
            if collab.partner_id:
                project_collabs = ProjectCollab.search([
                    ('partner_id', '=', collab.partner_id.id)
                ])
                collab.project_ids = project_collabs.mapped('project_id')
            else:
                collab.project_ids = False

    def _compute_project_stats(self):
        for collab in self:
            collab.project_count = len(collab.project_ids)
            if collab.user_id:
                tasks = self.env['project.task'].search([
                    ('user_ids', 'in', collab.user_id.id)
                ])
                collab.task_count = len(tasks)
            else:
                collab.task_count = 0

    def _compute_hours_worked(self):
        """Total de horas trabajadas en timesheet"""
        for collab in self:
            if collab.user_id:
                timesheets = self.env['account.analytic.line'].search([
                    ('user_id', '=', collab.user_id.id),
                    ('project_id', '!=', False),
                ])
                collab.hours_worked = sum(timesheets.mapped('unit_amount'))
            else:
                collab.hours_worked = 0

    def _compute_hours_this_week(self):
        """Horas trabajadas esta semana"""
        from datetime import datetime, timedelta
        today = datetime.today()
        start_of_week = today - timedelta(days=today.weekday())

        for collab in self:
            if collab.user_id:
                timesheets = self.env['account.analytic.line'].search([
                    ('user_id', '=', collab.user_id.id),
                    ('project_id', '!=', False),
                    ('date', '>=', start_of_week.date()),
                ])
                collab.hours_this_week = sum(timesheets.mapped('unit_amount'))
            else:
                collab.hours_this_week = 0

    # === ACCIONES ===
    def action_activate(self):
        """Activar colaborador: crear usuario portal si no existe"""
        self.ensure_one()

        if not self.partner_id.email:
            raise UserError(_('El contacto debe tener un email para crear usuario de portal.'))

        # Crear usuario de portal si no existe
        if not self.partner_id.user_ids:
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': self.partner_id.name,
                'login': self.partner_id.email,
                'email': self.partner_id.email,
                'partner_id': self.partner_id.id,
                'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            })
            _logger.info(f"Creado usuario portal para colaborador: {user.login}")

        self.state = 'active'
        self.hire_date = fields.Date.today()

        # Agregar a tipos de cita si aplica
        self._add_to_appointment_types()

        # Enviar email de bienvenida
        self._send_welcome_email()

    def action_pause(self):
        """Pausar colaborador temporalmente"""
        self.state = 'paused'
        self._remove_from_appointment_types()

    def action_reactivate(self):
        """Reactivar colaborador pausado"""
        self.state = 'active'
        self._add_to_appointment_types()

    def action_deactivate(self):
        """Desactivar colaborador"""
        self.state = 'inactive'
        self.termination_date = fields.Date.today()
        self._remove_from_appointment_types()

    def action_schedule_interview(self):
        """Cambiar a estado entrevista"""
        self.state = 'interview'

    def _add_to_appointment_types(self):
        """Agregar usuario a los tipos de cita que atiende"""
        if not self.user_id or not self.appointment_type_ids:
            return

        for apt_type in self.appointment_type_ids:
            if self.user_id not in apt_type.staff_user_ids:
                apt_type.staff_user_ids = [(4, self.user_id.id)]

    def _remove_from_appointment_types(self):
        """Remover usuario de los tipos de cita"""
        if not self.user_id:
            return

        for apt_type in self.appointment_type_ids:
            if self.user_id in apt_type.staff_user_ids:
                apt_type.staff_user_ids = [(3, self.user_id.id)]

    def _send_welcome_email(self):
        """Enviar email de bienvenida al colaborador"""
        template = self.env.ref(
            'saas_team.email_collaborator_welcome',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

    def action_share_project(self, project):
        """Compartir un proyecto con el colaborador usando project sharing nativo"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_('El colaborador debe tener un contacto asociado.'))

        # Verificar si ya tiene acceso
        existing = self.env['project.collaborator'].search([
            ('project_id', '=', project.id),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)

        if existing:
            _logger.info(f"Colaborador {self.name} ya tiene acceso a {project.name}")
            return existing

        # Crear acceso usando project.collaborator nativo
        project_collab = self.env['project.collaborator'].create({
            'project_id': project.id,
            'partner_id': self.partner_id.id,
            'limited_access': False,  # Acceso completo de edición
        })

        _logger.info(f"Compartido proyecto {project.name} con colaborador {self.name}")
        return project_collab

    def action_view_projects(self):
        """Ver proyectos del colaborador"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Proyectos de %s') % self.name,
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.project_ids.ids)],
        }

    def action_view_timesheets(self):
        """Ver timesheets del colaborador"""
        self.ensure_one()
        if not self.user_id:
            raise UserError(_('El colaborador no tiene usuario de portal.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Horas de %s') % self.name,
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [
                ('user_id', '=', self.user_id.id),
                ('project_id', '!=', False),
            ],
        }

    def action_create_payment(self):
        """Crear pago para el colaborador"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear Pago'),
            'res_model': 'saas.collaborator.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_collaborator_id': self.id,
                'default_amount': self.balance,
            },
        }
