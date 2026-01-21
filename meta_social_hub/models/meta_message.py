# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class MetaMessage(models.Model):
    """
    Unified message model for all Meta platform messages.
    Provides a common interface regardless of the source platform.
    """
    _name = 'meta.message'
    _description = 'Meta Message'
    _order = 'create_date asc, id asc'

    # Conversation reference
    conversation_id = fields.Many2one(
        'meta.conversation',
        string='Conversation',
        required=True,
        ondelete='cascade',
        index=True
    )
    channel_id = fields.Many2one(
        'meta.channel',
        related='conversation_id.channel_id',
        store=True
    )
    channel_type = fields.Selection(
        related='conversation_id.channel_type',
        store=True,
        index=True
    )

    # Message direction
    message_type = fields.Selection([
        ('inbound', 'Received'),
        ('outbound', 'Sent'),
    ], string='Direction', required=True, default='outbound', index=True)

    # Content
    body = fields.Html(string='Message Body')
    body_text = fields.Text(
        string='Plain Text',
        compute='_compute_body_text',
        store=True
    )

    # Attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'meta_message_attachment_rel',
        'message_id',
        'attachment_id',
        string='Attachments'
    )
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )

    # State tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('outgoing', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('received', 'Received'),  # For inbound messages
    ], string='Status', default='draft', required=True, tracking=True, index=True)

    failure_reason = fields.Text(string='Failure Reason')

    # External message IDs
    external_id = fields.Char(
        string='External Message ID',
        index=True,
        help='Message ID from the Meta platform'
    )

    # Reference to native Odoo messages (for integration)
    mail_message_id = fields.Many2one(
        'mail.message',
        string='Mail Message',
        help='Link to Odoo mail.message for tracking'
    )
    whatsapp_message_id = fields.Many2one(
        'whatsapp.message',
        string='WhatsApp Message',
        help='Link to native WhatsApp message'
    )

    # Products sent in this message
    product_ids = fields.Many2many(
        'product.product',
        'meta_message_product_rel',
        'message_id',
        'product_id',
        string='Products Sent'
    )

    # Author information
    author_type = fields.Selection([
        ('customer', 'Customer'),
        ('agent', 'Agent'),
        ('bot', 'Bot'),
    ], string='Author Type', compute='_compute_author_type', store=True)

    author_partner_id = fields.Many2one(
        'res.partner',
        string='Author Partner',
        help='For outbound messages, the agent\'s partner'
    )
    author_user_id = fields.Many2one(
        'res.users',
        string='Author User',
        help='For outbound messages, the agent user'
    )

    # Timestamps
    sent_date = fields.Datetime(string='Sent At')
    delivered_date = fields.Datetime(string='Delivered At')
    read_date = fields.Datetime(string='Read At')

    # Reply reference
    reply_to_id = fields.Many2one(
        'meta.message',
        string='Reply To',
        help='Message this is a reply to'
    )

    # Reactions (for platforms that support them)
    reaction = fields.Char(string='Reaction Emoji')

    @api.depends('body')
    def _compute_body_text(self):
        for msg in self:
            msg.body_text = html2plaintext(msg.body or '')

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for msg in self:
            msg.attachment_count = len(msg.attachment_ids)

    @api.depends('message_type', 'author_user_id')
    def _compute_author_type(self):
        for msg in self:
            if msg.message_type == 'inbound':
                msg.author_type = 'customer'
            elif msg.author_user_id:
                msg.author_type = 'agent'
            else:
                msg.author_type = 'bot'

    @api.model_create_multi
    def create(self, vals_list):
        """Set default author for outbound messages and update conversation"""
        for vals in vals_list:
            if vals.get('message_type') == 'outbound' and not vals.get('author_user_id'):
                vals['author_user_id'] = self.env.user.id
                vals['author_partner_id'] = self.env.user.partner_id.id

            # Set state for inbound messages
            if vals.get('message_type') == 'inbound':
                vals.setdefault('state', 'received')

        messages = super().create(vals_list)

        # Update conversation states
        for msg in messages:
            if msg.message_type == 'inbound' and msg.conversation_id.state == 'resolved':
                # Reopen if new inbound message on resolved conversation
                msg.conversation_id.write({'state': 'open'})

        return messages

    def action_send(self):
        """Send this message through the appropriate channel"""
        self.ensure_one()
        if self.state not in ['draft', 'failed']:
            raise UserError(_('Only draft or failed messages can be sent.'))

        self.write({'state': 'outgoing'})

        try:
            if self.channel_type == 'whatsapp':
                self._send_whatsapp()
            elif self.channel_type == 'facebook_messenger':
                self._send_messenger()
            elif self.channel_type == 'instagram':
                self._send_instagram_dm()
            else:
                raise UserError(_('Sending not supported for this channel type.'))
        except Exception as e:
            self.write({
                'state': 'failed',
                'failure_reason': str(e)
            })
            raise

    def _send_whatsapp(self):
        """Send message via WhatsApp"""
        self.ensure_one()
        wa_account = self.channel_id.whatsapp_account_id
        if not wa_account:
            raise UserError(_('No WhatsApp account configured for this channel.'))

        # Use the native WhatsApp API
        from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi

        wa_api = WhatsAppApi(wa_account)

        # Prepare message
        phone = self.conversation_id.phone
        if not phone:
            raise UserError(_('No phone number for this conversation.'))

        # Send text message
        result = wa_api._send_whatsapp(
            number=phone,
            message_type='text',
            send_vals={'body': self.body_text},
            parent_message_id=False
        )

        self.write({
            'state': 'sent',
            'external_id': result.get('messages', [{}])[0].get('id'),
            'sent_date': fields.Datetime.now(),
        })

    def _send_messenger(self):
        """Send message via Facebook Messenger"""
        self.ensure_one()
        channel = self.channel_id

        if not channel.facebook_access_token:
            raise UserError(_('No access token for this Facebook page.'))

        endpoint = self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED
        url = f"{endpoint}/{channel.facebook_page_id}/messages"

        payload = {
            'recipient': {'id': self.conversation_id.external_id},
            'message': {'text': self.body_text},
            'messaging_type': 'RESPONSE',
        }

        response = requests.post(url, params={
            'access_token': channel.facebook_access_token
        }, json=payload, timeout=30)

        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', 'Unknown error')
            raise UserError(_('Messenger API Error: %s') % error)

        result = response.json()
        self.write({
            'state': 'sent',
            'external_id': result.get('message_id'),
            'sent_date': fields.Datetime.now(),
        })

    def _send_instagram_dm(self):
        """Send message via Instagram Direct"""
        self.ensure_one()
        channel = self.channel_id

        if not channel.facebook_access_token:
            raise UserError(_('No access token for this Instagram account.'))

        endpoint = self.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED
        url = f"{endpoint}/{channel.instagram_account_id}/messages"

        payload = {
            'recipient': {'id': self.conversation_id.external_id},
            'message': {'text': self.body_text},
        }

        response = requests.post(url, params={
            'access_token': channel.facebook_access_token
        }, json=payload, timeout=30)

        if response.status_code != 200:
            error = response.json().get('error', {}).get('message', 'Unknown error')
            raise UserError(_('Instagram API Error: %s') % error)

        result = response.json()
        self.write({
            'state': 'sent',
            'external_id': result.get('message_id'),
            'sent_date': fields.Datetime.now(),
        })

    def action_retry_send(self):
        """Retry sending a failed message"""
        self.ensure_one()
        if self.state != 'failed':
            raise UserError(_('Only failed messages can be retried.'))
        self.action_send()

    def action_mark_read(self):
        """Mark message as read"""
        self.filtered(lambda m: m.state != 'read').write({
            'state': 'read',
            'read_date': fields.Datetime.now()
        })

    def update_status(self, status, timestamp=None):
        """Update message status from webhook callback"""
        status_mapping = {
            'sent': 'sent',
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
        }

        new_state = status_mapping.get(status)
        if not new_state:
            return

        vals = {'state': new_state}
        if new_state == 'sent':
            vals['sent_date'] = timestamp or fields.Datetime.now()
        elif new_state == 'delivered':
            vals['delivered_date'] = timestamp or fields.Datetime.now()
        elif new_state == 'read':
            vals['read_date'] = timestamp or fields.Datetime.now()

        self.write(vals)

    @api.model
    def create_from_webhook(self, conversation, external_id, body, message_type='inbound',
                           attachments=None, reply_to_external_id=None):
        """
        Create a message from webhook data.
        This is the main entry point for incoming messages.
        """
        vals = {
            'conversation_id': conversation.id,
            'external_id': external_id,
            'body': Markup('<p>%s</p>') % body if body else '',
            'message_type': message_type,
            'state': 'received' if message_type == 'inbound' else 'sent',
        }

        # Handle reply reference
        if reply_to_external_id:
            reply_to = self.search([
                ('conversation_id', '=', conversation.id),
                ('external_id', '=', reply_to_external_id)
            ], limit=1)
            if reply_to:
                vals['reply_to_id'] = reply_to.id

        message = self.create(vals)

        # Handle attachments
        if attachments:
            attachment_records = []
            for att in attachments:
                attachment = self.env['ir.attachment'].create({
                    'name': att.get('filename', 'attachment'),
                    'datas': att.get('data'),
                    'mimetype': att.get('mimetype'),
                    'res_model': 'meta.message',
                    'res_id': message.id,
                })
                attachment_records.append(attachment.id)
            message.write({'attachment_ids': [(6, 0, attachment_records)]})

        return message

    def _format_product_message(self, products, include_price=True, include_image=True):
        """
        Format products for sending as a message.
        Returns formatted HTML body.
        """
        if not products:
            return ''

        lines = []
        for product in products:
            line = f"<strong>{product.name}</strong>"
            if product.default_code:
                line += f" [{product.default_code}]"
            if include_price and product.lst_price:
                currency = product.currency_id or self.env.company.currency_id
                line += f"<br/>Price: {currency.symbol}{product.lst_price:,.2f}"
            if product.description_sale:
                line += f"<br/>{product.description_sale}"
            lines.append(line)

        return Markup('<br/><br/>').join(lines)
