# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MetaConversation(models.Model):
    """
    Unified conversation model that aggregates messages from all Meta platforms.
    Each conversation represents a chat thread with a single external user.
    """
    _name = 'meta.conversation'
    _description = 'Meta Conversation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_message_date desc, id desc'

    name = fields.Char(
        string='Conversation',
        compute='_compute_name',
        store=True
    )
    active = fields.Boolean(default=True)

    # Channel reference
    channel_id = fields.Many2one(
        'meta.channel',
        string='Channel',
        required=True,
        ondelete='cascade',
        index=True
    )
    channel_type = fields.Selection(
        related='channel_id.channel_type',
        store=True,
        index=True
    )

    # External contact information
    external_id = fields.Char(
        string='External User ID',
        required=True,
        index=True,
        help='User ID from the Meta platform (Facebook PSID, Instagram ID, WhatsApp phone)'
    )
    external_name = fields.Char(
        string='External Name',
        help='Name of the external user as provided by Meta'
    )
    external_avatar = fields.Image(
        string='Avatar',
        max_width=128,
        max_height=128
    )
    phone = fields.Char(
        string='Phone Number',
        index=True,
        help='Phone number for WhatsApp conversations'
    )

    # Link to Odoo partner
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        index=True,
        tracking=True
    )
    partner_name = fields.Char(
        related='partner_id.name',
        string='Contact Name'
    )
    partner_email = fields.Char(
        related='partner_id.email',
        string='Contact Email'
    )
    partner_phone = fields.Char(
        related='partner_id.phone',
        string='Contact Phone'
    )

    # State management
    state = fields.Selection([
        ('new', 'New'),
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
    ], string='Status', default='new', required=True, tracking=True, index=True)

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1', tracking=True)

    # Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        tracking=True,
        index=True
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        tracking=True
    )

    # Messages
    message_meta_ids = fields.One2many(
        'meta.message',
        'conversation_id',
        string='Chat Messages'
    )
    message_count = fields.Integer(
        string='Messages',
        compute='_compute_message_stats'
    )
    unread_count = fields.Integer(
        string='Unread',
        compute='_compute_message_stats',
        store=True
    )
    last_message_date = fields.Datetime(
        string='Last Message',
        compute='_compute_message_stats',
        store=True,
        index=True
    )
    last_message_preview = fields.Char(
        string='Last Message Preview',
        compute='_compute_message_stats',
        store=True
    )
    last_message_direction = fields.Selection([
        ('inbound', 'Received'),
        ('outbound', 'Sent'),
    ], string='Last Direction', compute='_compute_message_stats', store=True)

    # Time tracking
    first_response_time = fields.Float(
        string='First Response Time (hours)',
        help='Time between first customer message and first agent response'
    )
    resolution_time = fields.Float(
        string='Resolution Time (hours)',
        help='Time between conversation start and resolution'
    )

    # Tags
    tag_ids = fields.Many2many(
        'meta.conversation.tag',
        string='Tags'
    )

    # Related records in other modules
    lead_ids = fields.One2many(
        'crm.lead',
        'meta_conversation_id',
        string='Leads/Opportunities'
    )
    lead_count = fields.Integer(
        string='Lead Count',
        compute='_compute_related_counts'
    )

    sale_order_ids = fields.One2many(
        'sale.order',
        'meta_conversation_id',
        string='Sales Orders'
    )
    sale_order_count = fields.Integer(
        string='Order Count',
        compute='_compute_related_counts'
    )

    ticket_ids = fields.One2many(
        'helpdesk.ticket',
        'meta_conversation_id',
        string='Tickets'
    )
    ticket_count = fields.Integer(
        string='Ticket Count',
        compute='_compute_related_counts'
    )

    # Reference to native Odoo discuss channel (for WhatsApp integration)
    discuss_channel_id = fields.Many2one(
        'discuss.channel',
        string='Discuss Channel',
        help='Link to native Odoo discuss channel for WhatsApp'
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='channel_id.company_id',
        store=True
    )

    _sql_constraints = [
        ('unique_external_channel', 'UNIQUE(channel_id, external_id)',
         'A conversation already exists for this external user on this channel.'),
    ]

    @api.depends('external_name', 'partner_id', 'phone', 'channel_type')
    def _compute_name(self):
        for conv in self:
            if conv.partner_id:
                name = conv.partner_id.name
            elif conv.external_name:
                name = conv.external_name
            elif conv.phone:
                name = conv.phone
            else:
                name = conv.external_id or _('Unknown')

            # Add channel type indicator
            type_labels = {
                'facebook_page': 'FB',
                'facebook_messenger': 'Messenger',
                'instagram': 'IG',
                'whatsapp': 'WA',
            }
            type_label = type_labels.get(conv.channel_type, '')
            conv.name = f"[{type_label}] {name}" if type_label else name

    @api.depends('message_meta_ids', 'message_meta_ids.create_date',
                 'message_meta_ids.message_type', 'message_meta_ids.state')
    def _compute_message_stats(self):
        for conv in self:
            messages = conv.message_meta_ids.sorted('create_date', reverse=True)
            conv.message_count = len(messages)

            # Count unread (inbound messages not yet read)
            unread = messages.filtered(
                lambda m: m.message_type == 'inbound' and m.state != 'read'
            )
            conv.unread_count = len(unread)

            # Last message info
            if messages:
                last_msg = messages[0]
                conv.last_message_date = last_msg.create_date
                conv.last_message_direction = last_msg.message_type
                # Preview: strip HTML and truncate
                body = last_msg.body_text or ''
                conv.last_message_preview = body[:100] + '...' if len(body) > 100 else body
            else:
                conv.last_message_date = False
                conv.last_message_preview = False
                conv.last_message_direction = False

    @api.depends('lead_ids', 'sale_order_ids', 'ticket_ids')
    def _compute_related_counts(self):
        for conv in self:
            conv.lead_count = len(conv.lead_ids)
            conv.sale_order_count = len(conv.sale_order_ids)
            conv.ticket_count = len(conv.ticket_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-link to partner if phone matches"""
        for vals in vals_list:
            if vals.get('phone') and not vals.get('partner_id'):
                partner = self.env['res.partner'].search([
                    '|',
                    ('phone', 'ilike', vals['phone']),
                    ('mobile', 'ilike', vals['phone'])
                ], limit=1)
                if partner:
                    vals['partner_id'] = partner.id
        return super().create(vals_list)

    def write(self, vals):
        """Track state changes for metrics"""
        if 'state' in vals and vals['state'] == 'resolved':
            for conv in self:
                if conv.state != 'resolved' and conv.create_date:
                    # Calculate resolution time
                    delta = fields.Datetime.now() - conv.create_date
                    vals['resolution_time'] = delta.total_seconds() / 3600
        return super().write(vals)

    def action_open(self):
        """Mark conversation as open (being handled)"""
        self.write({
            'state': 'open',
            'user_id': self.env.user.id if not self.user_id else self.user_id.id
        })

    def action_pending(self):
        """Mark conversation as pending (waiting for customer)"""
        self.write({'state': 'pending'})

    def action_resolve(self):
        """Mark conversation as resolved"""
        self.write({'state': 'resolved'})

    def action_reopen(self):
        """Reopen a resolved conversation"""
        self.write({'state': 'open'})

    def action_assign_to_me(self):
        """Assign conversation to current user"""
        self.write({
            'user_id': self.env.user.id,
            'state': 'open' if self.state == 'new' else self.state
        })

    def action_view_messages(self):
        """Open message list view"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Messages - %s') % self.name,
            'res_model': 'meta.message',
            'view_mode': 'list,form',
            'domain': [('conversation_id', '=', self.id)],
            'context': {'default_conversation_id': self.id},
        }

    def action_create_lead(self):
        """Open wizard to create a CRM lead from this conversation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Lead'),
            'res_model': 'meta.create.lead.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
                'default_name': self.name,
                'default_partner_id': self.partner_id.id,
                'default_phone': self.phone or self.partner_phone,
            },
        }

    def action_create_ticket(self):
        """Open wizard to create a helpdesk ticket from this conversation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Ticket'),
            'res_model': 'meta.create.ticket.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }

    def action_send_product(self):
        """Open wizard to send products to the customer"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Products'),
            'res_model': 'meta.send.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.id,
            },
        }

    def action_view_partner(self):
        """Open linked partner form"""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('No contact linked to this conversation.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.partner_id.name,
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
        }

    def action_view_leads(self):
        """View related leads"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leads'),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('meta_conversation_id', '=', self.id)],
            'context': {'default_meta_conversation_id': self.id},
        }

    def action_view_orders(self):
        """View related sales orders"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Orders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('meta_conversation_id', '=', self.id)],
            'context': {'default_meta_conversation_id': self.id},
        }

    def action_view_tickets(self):
        """View related helpdesk tickets"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tickets'),
            'res_model': 'helpdesk.ticket',
            'view_mode': 'list,form',
            'domain': [('meta_conversation_id', '=', self.id)],
            'context': {'default_meta_conversation_id': self.id},
        }

    def _find_or_create_partner(self):
        """Find or create a partner for this conversation"""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id

        Partner = self.env['res.partner']
        partner = False

        # Try to find by phone
        if self.phone:
            partner = Partner.search([
                '|',
                ('phone', 'ilike', self.phone),
                ('mobile', 'ilike', self.phone)
            ], limit=1)

        # Create if not found
        if not partner:
            vals = {
                'name': self.external_name or self.phone or self.external_id,
            }
            if self.phone:
                vals['mobile'] = self.phone
            if self.external_avatar:
                vals['image_1920'] = self.external_avatar

            # Set social IDs based on channel type
            if self.channel_type == 'whatsapp':
                vals['whatsapp_id'] = self.external_id
            elif self.channel_type in ['facebook_page', 'facebook_messenger']:
                vals['facebook_id'] = self.external_id
            elif self.channel_type == 'instagram':
                vals['instagram_id'] = self.external_id

            partner = Partner.create(vals)

        self.partner_id = partner
        return partner

    @api.model
    def get_or_create_conversation(self, channel_id, external_id, external_name=None,
                                   phone=None, avatar=None):
        """
        Get existing conversation or create a new one.
        This is the main entry point for creating conversations from webhooks.
        """
        conversation = self.search([
            ('channel_id', '=', channel_id),
            ('external_id', '=', external_id)
        ], limit=1)

        if conversation:
            # Update info if changed
            update_vals = {}
            if external_name and external_name != conversation.external_name:
                update_vals['external_name'] = external_name
            if phone and phone != conversation.phone:
                update_vals['phone'] = phone
            if avatar and avatar != conversation.external_avatar:
                update_vals['external_avatar'] = avatar
            if update_vals:
                conversation.write(update_vals)
        else:
            # Create new conversation
            conversation = self.create({
                'channel_id': channel_id,
                'external_id': external_id,
                'external_name': external_name,
                'phone': phone,
                'external_avatar': avatar,
                'state': 'new',
            })

        return conversation
