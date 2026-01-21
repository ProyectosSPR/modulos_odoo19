# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Messenger Webhook Configuration
    meta_messenger_verify_token = fields.Char(
        string='Messenger Verify Token',
        config_parameter='meta_social_hub.messenger_verify_token',
        help='Token used to verify Facebook Messenger webhook subscription'
    )

    # Default Settings
    meta_auto_create_partner = fields.Boolean(
        string='Auto-create Contacts',
        config_parameter='meta_social_hub.auto_create_partner',
        default=True,
        help='Automatically create contacts from unknown senders'
    )

    meta_default_team_id = fields.Many2one(
        'crm.team',
        string='Default Sales Team',
        config_parameter='meta_social_hub.default_team_id',
        help='Default sales team for new conversations'
    )

    # Notifications
    meta_notify_new_conversation = fields.Boolean(
        string='Notify on New Conversation',
        config_parameter='meta_social_hub.notify_new_conversation',
        default=True,
        help='Send notification when a new conversation starts'
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()

        res.update(
            meta_messenger_verify_token=params.get_param(
                'meta_social_hub.messenger_verify_token', default=''),
            meta_auto_create_partner=params.get_param(
                'meta_social_hub.auto_create_partner', default='True') == 'True',
            meta_notify_new_conversation=params.get_param(
                'meta_social_hub.notify_new_conversation', default='True') == 'True',
        )

        # Get team_id
        team_id = params.get_param('meta_social_hub.default_team_id', default=False)
        if team_id:
            res['meta_default_team_id'] = int(team_id)

        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()

        params.set_param('meta_social_hub.messenger_verify_token',
                        self.meta_messenger_verify_token or '')
        params.set_param('meta_social_hub.auto_create_partner',
                        str(self.meta_auto_create_partner))
        params.set_param('meta_social_hub.notify_new_conversation',
                        str(self.meta_notify_new_conversation))
        params.set_param('meta_social_hub.default_team_id',
                        str(self.meta_default_team_id.id) if self.meta_default_team_id else '')
