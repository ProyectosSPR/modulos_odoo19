# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class CreateTicketWizard(models.TransientModel):
    """Wizard to create a helpdesk ticket from a Meta conversation"""
    _name = 'meta.create.ticket.wizard'
    _description = 'Create Ticket from Conversation'

    conversation_id = fields.Many2one(
        'meta.conversation',
        string='Conversation',
        required=True
    )

    name = fields.Char(
        string='Ticket Subject',
        required=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer'
    )

    team_id = fields.Many2one(
        'helpdesk.team',
        string='Helpdesk Team',
        required=True
    )

    ticket_type_id = fields.Many2one(
        'helpdesk.ticket.type',
        string='Ticket Type'
    )

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='1')

    description = fields.Html(
        string='Description',
        help='Ticket description'
    )

    include_conversation_history = fields.Boolean(
        string='Include Conversation History',
        default=True,
        help='Add conversation messages to ticket description'
    )

    @api.onchange('conversation_id')
    def _onchange_conversation_id(self):
        if self.conversation_id:
            conv = self.conversation_id

            # Set default name from last inbound message
            last_message = self.env['meta.message'].search([
                ('conversation_id', '=', conv.id),
                ('message_type', '=', 'inbound'),
            ], limit=1, order='create_date desc')

            if last_message and last_message.body_text:
                # Use first line or first 100 chars as subject
                first_line = last_message.body_text.split('\n')[0]
                self.name = first_line[:100] if len(first_line) > 100 else first_line
            else:
                self.name = _('Ticket from %s') % conv.name

            # Set partner
            self.partner_id = conv.partner_id

            # Set default team
            if not self.team_id:
                default_team = self.env['helpdesk.team'].search([], limit=1)
                if default_team:
                    self.team_id = default_team

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            # Reset ticket type when team changes
            self.ticket_type_id = False

    def action_create(self):
        """Create the helpdesk ticket"""
        self.ensure_one()

        # Create partner if needed
        partner = self.partner_id
        if not partner:
            partner = self.conversation_id._find_or_create_partner()

        # Build description
        description = self.description or ''

        if self.include_conversation_history:
            # Add recent messages to description
            messages = self.env['meta.message'].search([
                ('conversation_id', '=', self.conversation_id.id)
            ], order='create_date desc', limit=20)

            if messages:
                history_html = '<h4>Conversation History</h4><ul>'
                for msg in reversed(messages):
                    direction = 'Agent' if msg.message_type == 'outbound' else 'Customer'
                    date_str = msg.create_date.strftime('%Y-%m-%d %H:%M') if msg.create_date else ''
                    history_html += f'<li><strong>[{date_str}] {direction}:</strong> {msg.body or ""}</li>'
                history_html += '</ul>'

                description = f"{description}<br/><hr/>{history_html}"

        # Add source information
        source_html = f"""
        <hr/>
        <p><strong>Source:</strong></p>
        <ul>
            <li>Channel: {self.conversation_id.channel_id.name}</li>
            <li>Type: {dict(self.conversation_id._fields['channel_type'].selection).get(self.conversation_id.channel_type, '')}</li>
            <li>Phone: {self.conversation_id.phone or 'N/A'}</li>
        </ul>
        """
        description += source_html

        # Create ticket
        ticket_vals = {
            'name': self.name,
            'partner_id': partner.id if partner else False,
            'team_id': self.team_id.id,
            'ticket_type_id': self.ticket_type_id.id if self.ticket_type_id else False,
            'priority': self.priority,
            'description': description,
            'meta_conversation_id': self.conversation_id.id,
        }

        ticket = self.env['helpdesk.ticket'].create(ticket_vals)

        # Update conversation partner if created
        if partner and not self.conversation_id.partner_id:
            self.conversation_id.partner_id = partner

        # Return action to open the new ticket
        return {
            'type': 'ir.actions.act_window',
            'name': ticket.name,
            'res_model': 'helpdesk.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }
