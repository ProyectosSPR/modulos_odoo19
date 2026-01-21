# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class CrmLead(models.Model):
    """Extend CRM lead with Meta conversation tracking"""
    _inherit = 'crm.lead'

    meta_conversation_id = fields.Many2one(
        'meta.conversation',
        string='Source Conversation',
        help='Meta conversation that originated this lead'
    )
    meta_channel_type = fields.Selection(
        related='meta_conversation_id.channel_type',
        string='Source Channel',
        store=True
    )
    meta_channel_name = fields.Char(
        related='meta_conversation_id.channel_id.name',
        string='Channel Name'
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
                    'message': _('No conversation linked to this lead.'),
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversation'),
            'res_model': 'meta.conversation',
            'res_id': self.meta_conversation_id.id,
            'view_mode': 'form',
        }

    def action_send_via_meta(self):
        """Send a message via Meta channel"""
        self.ensure_one()
        if not self.meta_conversation_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No conversation linked to this lead.'),
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Message'),
            'res_model': 'meta.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': self.meta_conversation_id.id,
                'default_message_type': 'outbound',
            },
        }
