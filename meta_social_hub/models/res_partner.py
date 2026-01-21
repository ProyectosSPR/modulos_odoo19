# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResPartner(models.Model):
    """Extend partner with Meta social IDs and conversation tracking"""
    _inherit = 'res.partner'

    # Meta platform identifiers
    facebook_id = fields.Char(
        string='Facebook ID',
        help='Facebook Page-Scoped User ID (PSID)'
    )
    instagram_id = fields.Char(
        string='Instagram ID',
        help='Instagram-Scoped User ID (IGSID)'
    )
    whatsapp_id = fields.Char(
        string='WhatsApp ID',
        help='WhatsApp User ID (phone number)'
    )

    # Conversations
    meta_conversation_ids = fields.One2many(
        'meta.conversation',
        'partner_id',
        string='Meta Conversations'
    )
    meta_conversation_count = fields.Integer(
        string='Conversations',
        compute='_compute_meta_conversation_count'
    )

    # Quick stats
    meta_last_conversation_date = fields.Datetime(
        string='Last Conversation',
        compute='_compute_meta_conversation_count'
    )
    meta_channels = fields.Char(
        string='Active Channels',
        compute='_compute_meta_conversation_count',
        help='Channels where this contact has conversations'
    )

    @api.depends('meta_conversation_ids')
    def _compute_meta_conversation_count(self):
        for partner in self:
            conversations = partner.meta_conversation_ids
            partner.meta_conversation_count = len(conversations)

            if conversations:
                # Last conversation date
                latest = conversations.sorted('last_message_date', reverse=True)[:1]
                partner.meta_last_conversation_date = latest.last_message_date if latest else False

                # Active channels
                channel_types = set(conversations.mapped('channel_type'))
                type_labels = {
                    'facebook_page': 'FB',
                    'facebook_messenger': 'Messenger',
                    'instagram': 'Instagram',
                    'whatsapp': 'WhatsApp',
                }
                partner.meta_channels = ', '.join(
                    type_labels.get(ct, ct) for ct in channel_types if ct
                )
            else:
                partner.meta_last_conversation_date = False
                partner.meta_channels = False

    def action_view_meta_conversations(self):
        """Open conversations for this partner"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversations - %s') % self.name,
            'res_model': 'meta.conversation',
            'view_mode': 'kanban,list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_start_meta_conversation(self):
        """Start a new conversation with this partner"""
        self.ensure_one()

        # Check if we have contact info to start a conversation
        if not (self.facebook_id or self.instagram_id or self.whatsapp_id or self.mobile or self.phone):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('This contact has no Meta platform IDs or phone number.'),
                }
            }

        # If WhatsApp ID or phone available, try to find/create WhatsApp conversation
        if self.whatsapp_id or self.mobile or self.phone:
            phone = self.whatsapp_id or self.mobile or self.phone
            # Find a WhatsApp channel
            wa_channel = self.env['meta.channel'].search([
                ('channel_type', '=', 'whatsapp'),
                ('company_id', 'in', [False, self.env.company.id])
            ], limit=1)

            if wa_channel:
                conversation = self.env['meta.conversation'].get_or_create_conversation(
                    channel_id=wa_channel.id,
                    external_id=phone,
                    external_name=self.name,
                    phone=phone
                )
                conversation.partner_id = self.id
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Conversation - %s') % self.name,
                    'res_model': 'meta.conversation',
                    'res_id': conversation.id,
                    'view_mode': 'form',
                }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'message': _('No Meta channel configured. Please set up a channel first.'),
            }
        }

    @api.model
    def find_or_create_from_meta(self, channel_type, external_id, name=None, phone=None, avatar=None):
        """
        Find existing partner by Meta ID or phone, or create a new one.
        Used when receiving messages from unknown contacts.
        """
        partner = False

        # Try to find by Meta ID
        if channel_type == 'whatsapp' and external_id:
            partner = self.search([('whatsapp_id', '=', external_id)], limit=1)
        elif channel_type in ['facebook_page', 'facebook_messenger'] and external_id:
            partner = self.search([('facebook_id', '=', external_id)], limit=1)
        elif channel_type == 'instagram' and external_id:
            partner = self.search([('instagram_id', '=', external_id)], limit=1)

        # Try to find by phone
        if not partner and phone:
            partner = self.search([
                '|',
                ('phone', 'ilike', phone),
                ('mobile', 'ilike', phone)
            ], limit=1)

        # Create new partner if not found
        if not partner:
            vals = {
                'name': name or phone or external_id or _('Unknown Contact'),
            }

            if phone:
                vals['mobile'] = phone

            if avatar:
                vals['image_1920'] = avatar

            # Set Meta ID
            if channel_type == 'whatsapp':
                vals['whatsapp_id'] = external_id
            elif channel_type in ['facebook_page', 'facebook_messenger']:
                vals['facebook_id'] = external_id
            elif channel_type == 'instagram':
                vals['instagram_id'] = external_id

            partner = self.create(vals)

        return partner
