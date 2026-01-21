# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WhatsappAccount(models.Model):
    """
    Extend WhatsApp account to integrate with Meta Social Hub.
    Creates/links meta.channel automatically.
    """
    _inherit = 'whatsapp.account'

    meta_channel_id = fields.Many2one(
        'meta.channel',
        string='Meta Channel',
        readonly=True,
        help='Linked Meta Social Hub channel'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create linked meta.channel when WhatsApp account is created"""
        accounts = super().create(vals_list)

        for account in accounts:
            # Create meta channel for this WhatsApp account
            channel = self.env['meta.channel'].create({
                'name': account.name or f'WhatsApp - {account.phone_number}',
                'channel_type': 'whatsapp',
                'whatsapp_account_id': account.id,
                'company_id': account.allowed_company_ids[:1].id if account.allowed_company_ids else False,
            })
            account.meta_channel_id = channel.id

        return accounts

    def write(self, vals):
        """Update meta channel name if account name changes"""
        res = super().write(vals)

        if 'name' in vals:
            for account in self:
                if account.meta_channel_id:
                    account.meta_channel_id.name = account.name

        return res

    def unlink(self):
        """Delete linked meta channel when account is deleted"""
        channels = self.mapped('meta_channel_id')
        res = super().unlink()
        channels.unlink()
        return res

    def action_view_meta_conversations(self):
        """View conversations in Meta Social Hub"""
        self.ensure_one()
        if not self.meta_channel_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No Meta channel linked to this account.'),
                }
            }

        return self.meta_channel_id.action_view_conversations()

    def _sync_conversations_to_meta_hub(self):
        """
        Synchronize existing WhatsApp conversations (discuss.channel) to meta.conversation.
        This is useful for initial setup or periodic sync.
        """
        self.ensure_one()

        if not self.meta_channel_id:
            _logger.warning('Cannot sync: No meta channel for WhatsApp account %s', self.name)
            return

        # Find all WhatsApp discuss channels for this account
        DiscussChannel = self.env['discuss.channel'].sudo()
        wa_channels = DiscussChannel.search([
            ('channel_type', '=', 'whatsapp'),
            ('wa_account_id', '=', self.id),
        ])

        MetaConversation = self.env['meta.conversation'].sudo()

        synced_count = 0
        for discuss_channel in wa_channels:
            # Check if conversation already exists
            existing = MetaConversation.search([
                ('channel_id', '=', self.meta_channel_id.id),
                ('discuss_channel_id', '=', discuss_channel.id),
            ], limit=1)

            if existing:
                continue

            # Get partner info from discuss channel
            partner = discuss_channel.whatsapp_partner_id
            phone = discuss_channel.whatsapp_number

            # Create meta conversation
            MetaConversation.create({
                'channel_id': self.meta_channel_id.id,
                'external_id': phone or str(discuss_channel.id),
                'external_name': partner.name if partner else phone,
                'phone': phone,
                'partner_id': partner.id if partner else False,
                'discuss_channel_id': discuss_channel.id,
                'state': 'open',
            })
            synced_count += 1

        _logger.info('Synced %d WhatsApp conversations to Meta Hub for account %s',
                    synced_count, self.name)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Synchronized %d conversations.') % synced_count,
            }
        }
