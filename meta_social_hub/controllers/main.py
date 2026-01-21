# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MetaSocialHubController(http.Controller):
    """Main controller for Meta Social Hub"""

    @http.route('/meta_social_hub/conversation/<int:conversation_id>/messages',
                type='json', auth='user')
    def get_conversation_messages(self, conversation_id, offset=0, limit=50, **kwargs):
        """
        Get messages for a conversation (for lazy loading in UI).
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        messages = request.env['meta.message'].search([
            ('conversation_id', '=', conversation_id)
        ], offset=offset, limit=limit, order='create_date desc')

        return {
            'messages': [{
                'id': msg.id,
                'body': msg.body,
                'message_type': msg.message_type,
                'state': msg.state,
                'create_date': msg.create_date.isoformat() if msg.create_date else None,
                'author_name': msg.author_user_id.name if msg.author_user_id else msg.conversation_id.external_name,
                'attachments': [{
                    'id': att.id,
                    'name': att.name,
                    'mimetype': att.mimetype,
                } for att in msg.attachment_ids],
            } for msg in messages],
            'has_more': len(messages) == limit,
        }

    @http.route('/meta_social_hub/conversation/<int:conversation_id>/send',
                type='json', auth='user', methods=['POST'])
    def send_message(self, conversation_id, body, attachment_ids=None, **kwargs):
        """
        Send a message in a conversation.
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        # Create message
        message_vals = {
            'conversation_id': conversation_id,
            'message_type': 'outbound',
            'body': body,
            'state': 'draft',
        }

        if attachment_ids:
            message_vals['attachment_ids'] = [(6, 0, attachment_ids)]

        message = request.env['meta.message'].create(message_vals)

        # Try to send
        try:
            message.action_send()
            return {
                'success': True,
                'message_id': message.id,
                'state': message.state,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message_id': message.id,
            }

    @http.route('/meta_social_hub/conversation/<int:conversation_id>/mark_read',
                type='json', auth='user', methods=['POST'])
    def mark_conversation_read(self, conversation_id, **kwargs):
        """
        Mark all messages in a conversation as read.
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        # Mark all inbound messages as read
        messages = request.env['meta.message'].search([
            ('conversation_id', '=', conversation_id),
            ('message_type', '=', 'inbound'),
            ('state', '!=', 'read'),
        ])
        messages.action_mark_read()

        return {'success': True, 'marked_count': len(messages)}

    @http.route('/meta_social_hub/inbox/stats', type='json', auth='user')
    def get_inbox_stats(self, **kwargs):
        """
        Get inbox statistics for dashboard widgets.
        """
        Conversation = request.env['meta.conversation']

        # Get counts by state
        states = ['new', 'open', 'pending', 'resolved']
        state_counts = {}
        for state in states:
            state_counts[state] = Conversation.search_count([('state', '=', state)])

        # Get counts by channel type
        channel_types = ['facebook_page', 'facebook_messenger', 'instagram', 'whatsapp']
        channel_counts = {}
        for ct in channel_types:
            channel_counts[ct] = Conversation.search_count([
                ('channel_type', '=', ct),
                ('state', 'in', ['new', 'open'])
            ])

        # Total unread
        total_unread = sum(Conversation.search([
            ('state', 'in', ['new', 'open'])
        ]).mapped('unread_count'))

        # My assigned
        my_assigned = Conversation.search_count([
            ('user_id', '=', request.env.user.id),
            ('state', 'in', ['new', 'open', 'pending'])
        ])

        return {
            'state_counts': state_counts,
            'channel_counts': channel_counts,
            'total_unread': total_unread,
            'my_assigned': my_assigned,
        }

    @http.route('/meta_social_hub/quick_actions/create_lead',
                type='json', auth='user', methods=['POST'])
    def quick_create_lead(self, conversation_id, **kwargs):
        """
        Quickly create a lead from a conversation.
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        # Create partner if needed
        partner = conversation._find_or_create_partner()

        # Create lead
        lead = request.env['crm.lead'].create({
            'name': f"Lead from {conversation.name}",
            'partner_id': partner.id,
            'phone': conversation.phone or partner.phone,
            'meta_conversation_id': conversation.id,
            'description': f"Created from {conversation.channel_type} conversation",
        })

        return {
            'success': True,
            'lead_id': lead.id,
            'lead_name': lead.name,
        }

    @http.route('/meta_social_hub/quick_actions/create_ticket',
                type='json', auth='user', methods=['POST'])
    def quick_create_ticket(self, conversation_id, **kwargs):
        """
        Quickly create a helpdesk ticket from a conversation.
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        # Create partner if needed
        partner = conversation._find_or_create_partner()

        # Get last message as description
        last_message = request.env['meta.message'].search([
            ('conversation_id', '=', conversation_id),
            ('message_type', '=', 'inbound'),
        ], limit=1, order='create_date desc')

        # Create ticket
        ticket = request.env['helpdesk.ticket'].create({
            'name': f"Ticket from {conversation.name}",
            'partner_id': partner.id,
            'meta_conversation_id': conversation.id,
            'description': last_message.body_text if last_message else '',
        })

        return {
            'success': True,
            'ticket_id': ticket.id,
            'ticket_name': ticket.name,
        }

    @http.route('/meta_social_hub/quick_actions/assign_to_me',
                type='json', auth='user', methods=['POST'])
    def quick_assign_to_me(self, conversation_id, **kwargs):
        """
        Quickly assign a conversation to current user.
        """
        conversation = request.env['meta.conversation'].browse(conversation_id)
        if not conversation.exists():
            return {'error': 'Conversation not found'}

        conversation.action_assign_to_me()

        return {
            'success': True,
            'user_id': request.env.user.id,
            'user_name': request.env.user.name,
        }
