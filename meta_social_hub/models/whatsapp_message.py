# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from markupsafe import Markup
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WhatsappMessage(models.Model):
    """
    Extend WhatsApp message to sync with Meta Social Hub.
    Creates meta.message records for unified inbox view.
    """
    _inherit = 'whatsapp.message'

    meta_message_id = fields.Many2one(
        'meta.message',
        string='Meta Message',
        readonly=True,
        help='Linked Meta Social Hub message'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create linked meta.message when WhatsApp message is created"""
        messages = super().create(vals_list)

        for message in messages:
            message._create_meta_message()

        return messages

    def _create_meta_message(self):
        """Create corresponding meta.message record"""
        self.ensure_one()

        # Get the meta channel from WhatsApp account
        wa_account = self.wa_account_id
        if not wa_account or not wa_account.meta_channel_id:
            return

        meta_channel = wa_account.meta_channel_id

        # Find or create the conversation
        phone = self.mobile_number_formatted or self.mobile_number
        if not phone:
            return

        MetaConversation = self.env['meta.conversation'].sudo()
        conversation = MetaConversation.search([
            ('channel_id', '=', meta_channel.id),
            ('phone', '=', phone),
        ], limit=1)

        if not conversation:
            # Create new conversation
            conversation = MetaConversation.create({
                'channel_id': meta_channel.id,
                'external_id': phone,
                'phone': phone,
                'state': 'new',
            })

        # Map WhatsApp message state to meta message state
        state_mapping = {
            'outgoing': 'outgoing',
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'error': 'failed',
            'bounced': 'failed',
            'cancel': 'failed',
            'received': 'received',
        }

        # Get message body
        body = ''
        if self.mail_message_id and self.mail_message_id.body:
            body = self.mail_message_id.body
        elif self.free_text_json:
            # Template message with variables
            template = self.wa_template_id
            if template:
                body = Markup('<p>%s</p>') % (template.body or '')

        # Create meta message
        meta_message = self.env['meta.message'].sudo().create({
            'conversation_id': conversation.id,
            'message_type': self.message_type,
            'body': body,
            'external_id': self.msg_uid,
            'state': state_mapping.get(self.state, 'draft'),
            'whatsapp_message_id': self.id,
            'mail_message_id': self.mail_message_id.id if self.mail_message_id else False,
        })

        self.meta_message_id = meta_message.id

    def write(self, vals):
        """Update meta message when WhatsApp message status changes"""
        res = super().write(vals)

        if 'state' in vals:
            state_mapping = {
                'sent': 'sent',
                'delivered': 'delivered',
                'read': 'read',
                'error': 'failed',
                'bounced': 'failed',
            }
            new_meta_state = state_mapping.get(vals['state'])

            if new_meta_state:
                for message in self:
                    if message.meta_message_id:
                        update_vals = {'state': new_meta_state}
                        if new_meta_state == 'sent':
                            update_vals['sent_date'] = fields.Datetime.now()
                        elif new_meta_state == 'delivered':
                            update_vals['delivered_date'] = fields.Datetime.now()
                        elif new_meta_state == 'read':
                            update_vals['read_date'] = fields.Datetime.now()
                        elif new_meta_state == 'failed':
                            update_vals['failure_reason'] = message.failure_reason

                        message.meta_message_id.sudo().write(update_vals)

        return res
