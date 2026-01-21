# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HelpdeskTicket(models.Model):
    """Extend helpdesk ticket with Meta conversation tracking"""
    _inherit = 'helpdesk.ticket'

    meta_conversation_id = fields.Many2one(
        'meta.conversation',
        string='Source Conversation',
        help='Meta conversation that originated this ticket'
    )
    meta_channel_type = fields.Selection(
        related='meta_conversation_id.channel_type',
        string='Source Channel',
        store=True
    )

    def action_open_meta_conversation(self):
        """Open the source Meta conversation"""
        self.ensure_one()
        if not self.meta_conversation_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No conversation linked to this ticket.'),
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversation'),
            'res_model': 'meta.conversation',
            'res_id': self.meta_conversation_id.id,
            'view_mode': 'form',
        }

    def action_reply_via_meta(self):
        """Reply to customer via Meta channel"""
        self.ensure_one()
        if not self.meta_conversation_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No conversation linked to this ticket.'),
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Reply'),
            'res_model': 'meta.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.meta_conversation_id.id,
                'default_message_type': 'outbound',
            },
        }
