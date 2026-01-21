# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class CreateLeadWizard(models.TransientModel):
    """Wizard to create a CRM lead from a Meta conversation"""
    _name = 'meta.create.lead.wizard'
    _description = 'Create Lead from Conversation'

    conversation_id = fields.Many2one(
        'meta.conversation',
        string='Conversation',
        required=True
    )

    name = fields.Char(
        string='Lead Name',
        required=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer'
    )
    create_partner = fields.Boolean(
        string='Create Contact',
        default=False,
        help='Create a new contact if none exists'
    )

    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user
    )

    expected_revenue = fields.Monetary(
        string='Expected Revenue',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    description = fields.Text(
        string='Notes',
        help='Additional notes for the lead'
    )

    include_conversation_history = fields.Boolean(
        string='Include Conversation History',
        default=True,
        help='Add conversation messages to lead description'
    )

    @api.onchange('conversation_id')
    def _onchange_conversation_id(self):
        if self.conversation_id:
            conv = self.conversation_id

            # Set default name
            if not self.name:
                self.name = _('Lead from %s') % conv.name

            # Set partner and phone
            if conv.partner_id:
                self.partner_id = conv.partner_id
                self.phone = conv.partner_id.phone or conv.partner_id.mobile
                self.email = conv.partner_id.email
            else:
                self.phone = conv.phone
                self.create_partner = True

    def action_create(self):
        """Create the CRM lead"""
        self.ensure_one()

        # Create or get partner
        partner = self.partner_id
        if not partner and self.create_partner:
            partner = self.conversation_id._find_or_create_partner()

        # Build description
        description = self.description or ''

        if self.include_conversation_history:
            # Add recent messages to description
            messages = self.env['meta.message'].search([
                ('conversation_id', '=', self.conversation_id.id)
            ], order='create_date desc', limit=10)

            if messages:
                description += '\n\n--- Conversation History ---\n'
                for msg in reversed(messages):
                    direction = '→' if msg.message_type == 'outbound' else '←'
                    date_str = msg.create_date.strftime('%Y-%m-%d %H:%M') if msg.create_date else ''
                    description += f"\n[{date_str}] {direction} {msg.body_text or ''}"

        # Add source information
        description += f"\n\n--- Source ---\n"
        description += f"Channel: {self.conversation_id.channel_id.name}\n"
        description += f"Type: {dict(self.conversation_id._fields['channel_type'].selection).get(self.conversation_id.channel_type, '')}\n"

        # Create lead
        lead_vals = {
            'name': self.name,
            'partner_id': partner.id if partner else False,
            'phone': self.phone,
            'email_from': self.email,
            'team_id': self.team_id.id if self.team_id else False,
            'user_id': self.user_id.id if self.user_id else False,
            'expected_revenue': self.expected_revenue,
            'description': description,
            'meta_conversation_id': self.conversation_id.id,
        }

        lead = self.env['crm.lead'].create(lead_vals)

        # Update conversation partner if created
        if partner and not self.conversation_id.partner_id:
            self.conversation_id.partner_id = partner

        # Return action to open the new lead
        return {
            'type': 'ir.actions.act_window',
            'name': lead.name,
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }
