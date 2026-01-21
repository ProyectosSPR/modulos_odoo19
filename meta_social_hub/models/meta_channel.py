# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MetaChannel(models.Model):
    """
    Meta Channel represents a communication channel from Meta platforms.
    It can be linked to existing social.account (Facebook/Instagram) or
    whatsapp.account records, providing a unified interface.
    """
    _name = 'meta.channel'
    _description = 'Meta Channel (Facebook Page, Instagram, WhatsApp)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Channel Name', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    channel_type = fields.Selection([
        ('facebook_page', 'Facebook Page'),
        ('facebook_messenger', 'Facebook Messenger'),
        ('instagram', 'Instagram'),
        ('whatsapp', 'WhatsApp'),
    ], string='Channel Type', required=True, tracking=True)

    # Reference to existing Odoo social accounts
    social_account_id = fields.Many2one(
        'social.account',
        string='Social Account',
        help='Link to existing Facebook/Instagram social account',
        domain="[('media_type', 'in', ['facebook', 'instagram'])]"
    )

    whatsapp_account_id = fields.Many2one(
        'whatsapp.account',
        string='WhatsApp Account',
        help='Link to existing WhatsApp Business account'
    )

    # Facebook/Instagram specific fields (from social.account)
    facebook_page_id = fields.Char(
        string='Facebook Page ID',
        related='social_account_id.facebook_account_id',
        readonly=True
    )
    facebook_access_token = fields.Char(
        string='Page Access Token',
        related='social_account_id.facebook_access_token',
        readonly=True
    )

    # Messenger specific fields (for direct Messenger integration)
    messenger_enabled = fields.Boolean(
        string='Messenger Enabled',
        default=False,
        help='Enable Facebook Messenger for this page'
    )
    messenger_webhook_verified = fields.Boolean(
        string='Webhook Verified',
        default=False,
        readonly=True
    )

    # Instagram specific fields
    instagram_account_id = fields.Char(
        string='Instagram Account ID',
        help='Instagram Business Account ID'
    )
    instagram_username = fields.Char(
        string='Instagram Username',
        compute='_compute_instagram_info',
        store=True
    )

    # WhatsApp specific fields (from whatsapp.account)
    whatsapp_phone_number = fields.Char(
        string='WhatsApp Phone',
        related='whatsapp_account_id.phone_number',
        readonly=True
    )

    # Statistics
    conversation_count = fields.Integer(
        string='Conversations',
        compute='_compute_conversation_stats'
    )
    unread_count = fields.Integer(
        string='Unread Messages',
        compute='_compute_conversation_stats'
    )
    active_conversation_count = fields.Integer(
        string='Active Conversations',
        compute='_compute_conversation_stats'
    )

    # Image/Avatar
    image = fields.Image(
        string='Channel Image',
        max_width=128,
        max_height=128
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    # Conversations
    conversation_ids = fields.One2many(
        'meta.conversation',
        'channel_id',
        string='Conversations'
    )

    _sql_constraints = [
        ('unique_social_account', 'UNIQUE(social_account_id)',
         'A Meta Channel already exists for this social account.'),
        ('unique_whatsapp_account', 'UNIQUE(whatsapp_account_id)',
         'A Meta Channel already exists for this WhatsApp account.'),
    ]

    @api.depends('social_account_id', 'social_account_id.social_account_handle')
    def _compute_instagram_info(self):
        for channel in self:
            if channel.channel_type == 'instagram' and channel.social_account_id:
                channel.instagram_username = channel.social_account_id.social_account_handle
            else:
                channel.instagram_username = False

    @api.depends('conversation_ids', 'conversation_ids.state', 'conversation_ids.unread_count')
    def _compute_conversation_stats(self):
        for channel in self:
            conversations = channel.conversation_ids
            channel.conversation_count = len(conversations)
            channel.unread_count = sum(conversations.mapped('unread_count'))
            channel.active_conversation_count = len(
                conversations.filtered(lambda c: c.state in ['new', 'open'])
            )

    @api.onchange('channel_type')
    def _onchange_channel_type(self):
        """Clear irrelevant fields when channel type changes"""
        if self.channel_type in ['facebook_page', 'facebook_messenger', 'instagram']:
            self.whatsapp_account_id = False
        elif self.channel_type == 'whatsapp':
            self.social_account_id = False

    @api.constrains('channel_type', 'social_account_id', 'whatsapp_account_id')
    def _check_account_type(self):
        for channel in self:
            if channel.channel_type in ['facebook_page', 'facebook_messenger']:
                if not channel.social_account_id:
                    raise ValidationError(_(
                        'Facebook channels require a linked social account.'
                    ))
                if channel.social_account_id.media_type != 'facebook':
                    raise ValidationError(_(
                        'Facebook channels must be linked to a Facebook social account.'
                    ))
            elif channel.channel_type == 'instagram':
                if not channel.social_account_id:
                    raise ValidationError(_(
                        'Instagram channels require a linked social account.'
                    ))
                if channel.social_account_id.media_type != 'instagram':
                    raise ValidationError(_(
                        'Instagram channels must be linked to an Instagram social account.'
                    ))
            elif channel.channel_type == 'whatsapp':
                if not channel.whatsapp_account_id:
                    raise ValidationError(_(
                        'WhatsApp channels require a linked WhatsApp account.'
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        """Set default image from linked account if not provided"""
        for vals in vals_list:
            if not vals.get('image'):
                if vals.get('social_account_id'):
                    social_account = self.env['social.account'].browse(vals['social_account_id'])
                    vals['image'] = social_account.image
                elif vals.get('whatsapp_account_id'):
                    # WhatsApp accounts don't have images, could set a default
                    pass
        return super().create(vals_list)

    def action_view_conversations(self):
        """Open conversations for this channel"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversations - %s') % self.name,
            'res_model': 'meta.conversation',
            'view_mode': 'kanban,list,form',
            'domain': [('channel_id', '=', self.id)],
            'context': {'default_channel_id': self.id},
        }

    def action_test_connection(self):
        """Test connection to the Meta platform"""
        self.ensure_one()
        try:
            if self.channel_type == 'whatsapp':
                # Use WhatsApp's test connection
                return self.whatsapp_account_id.button_test_connection()
            elif self.channel_type in ['facebook_page', 'facebook_messenger']:
                # Test Facebook connection
                self._test_facebook_connection()
            elif self.channel_type == 'instagram':
                # Test Instagram connection
                self._test_instagram_connection()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _('Connection successful!'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        except Exception as e:
            raise UserError(_('Connection failed: %s') % str(e))

    def _test_facebook_connection(self):
        """Test Facebook Graph API connection"""
        if not self.facebook_access_token:
            raise UserError(_('No access token available for this Facebook page.'))

        endpoint = self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED
        url = f"{endpoint}/{self.facebook_page_id}"

        response = requests.get(url, params={
            'fields': 'id,name',
            'access_token': self.facebook_access_token
        }, timeout=10)

        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', 'Unknown error')
            raise UserError(_('Facebook API Error: %s') % error)

    def _test_instagram_connection(self):
        """Test Instagram Graph API connection"""
        if not self.facebook_access_token:
            raise UserError(_('No access token available for this Instagram account.'))

        endpoint = self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED
        url = f"{endpoint}/{self.instagram_account_id}"

        response = requests.get(url, params={
            'fields': 'id,username',
            'access_token': self.facebook_access_token
        }, timeout=10)

        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', 'Unknown error')
            raise UserError(_('Instagram API Error: %s') % error)

    def _get_channel_icon(self):
        """Return icon class for channel type"""
        icons = {
            'facebook_page': 'fa-facebook-square',
            'facebook_messenger': 'fa-facebook-messenger',
            'instagram': 'fa-instagram',
            'whatsapp': 'fa-whatsapp',
        }
        return icons.get(self.channel_type, 'fa-comments')
