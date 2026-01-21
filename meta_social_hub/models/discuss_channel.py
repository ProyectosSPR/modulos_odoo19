# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    """
    Extend discuss channel to sync WhatsApp conversations with Meta Social Hub.
    """
    _inherit = 'discuss.channel'

    meta_conversation_id = fields.Many2one(
        'meta.conversation',
        string='Meta Conversation',
        readonly=True,
        help='Linked Meta Social Hub conversation'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Link to meta conversation when WhatsApp channel is created"""
        channels = super().create(vals_list)

        for channel in channels:
            if channel.channel_type == 'whatsapp':
                channel._link_to_meta_conversation()

        return channels

    def _link_to_meta_conversation(self):
        """Create or link to a meta.conversation"""
        self.ensure_one()

        if self.channel_type != 'whatsapp':
            return

        if self.meta_conversation_id:
            return

        # Get WhatsApp account and its meta channel
        wa_account = self.wa_account_id
        if not wa_account or not wa_account.meta_channel_id:
            return

        meta_channel = wa_account.meta_channel_id

        # Find existing or create new meta conversation
        MetaConversation = self.env['meta.conversation'].sudo()
        phone = self.whatsapp_number

        conversation = MetaConversation.search([
            ('channel_id', '=', meta_channel.id),
            ('phone', '=', phone),
        ], limit=1)

        if not conversation:
            partner = self.whatsapp_partner_id
            conversation = MetaConversation.create({
                'channel_id': meta_channel.id,
                'external_id': phone or str(self.id),
                'external_name': partner.name if partner else phone,
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'discuss_channel_id': self.id,
                'state': 'new',
            })
        else:
            # Link existing conversation to this discuss channel
            conversation.write({'discuss_channel_id': self.id})

        self.meta_conversation_id = conversation.id

    def message_post(self, **kwargs):
        """
        Override to sync messages to meta.message.
        This captures messages posted directly to discuss channel.
        """
        message = super().message_post(**kwargs)

        # Sync to meta if this is a WhatsApp channel
        if self.channel_type == 'whatsapp' and self.meta_conversation_id:
            self._sync_message_to_meta(message, kwargs)

        return message

    def _sync_message_to_meta(self, mail_message, kwargs):
        """
        Sync a mail.message to meta.message for unified inbox.
        """
        if not self.meta_conversation_id:
            return

        # Determine message direction
        message_type = kwargs.get('message_type', 'comment')
        if message_type == 'whatsapp_message':
            # This is handled by whatsapp.message _create_meta_message
            return

        # For agent messages posted via discuss
        if mail_message.author_id == self.env.user.partner_id:
            direction = 'outbound'
        else:
            direction = 'inbound'

        # Check if meta message already exists (via whatsapp.message)
        existing = self.env['meta.message'].search([
            ('mail_message_id', '=', mail_message.id)
        ], limit=1)

        if existing:
            return

        # Create meta message
        self.env['meta.message'].sudo().create({
            'conversation_id': self.meta_conversation_id.id,
            'message_type': direction,
            'body': mail_message.body,
            'mail_message_id': mail_message.id,
            'state': 'sent' if direction == 'outbound' else 'received',
            'author_partner_id': mail_message.author_id.id if direction == 'outbound' else False,
            'author_user_id': self.env.user.id if direction == 'outbound' else False,
            'attachment_ids': [(6, 0, mail_message.attachment_ids.ids)],
        })
