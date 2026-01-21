# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Extend sale order with Meta conversation integration"""
    _inherit = 'sale.order'

    meta_conversation_id = fields.Many2one(
        'meta.conversation',
        string='Source Conversation',
        help='Meta conversation linked to this order'
    )
    meta_channel_type = fields.Selection(
        related='meta_conversation_id.channel_type',
        string='Channel Type'
    )

    def action_open_meta_conversation(self):
        """Open the linked Meta conversation"""
        self.ensure_one()
        if not self.meta_conversation_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No conversation linked to this order.'),
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Conversation'),
            'res_model': 'meta.conversation',
            'res_id': self.meta_conversation_id.id,
            'view_mode': 'form',
        }

    def action_send_quotation_via_meta(self):
        """Send quotation/order confirmation via Meta channel"""
        self.ensure_one()

        # Find conversation from partner if not directly linked
        conversation = self.meta_conversation_id
        if not conversation and self.partner_id:
            conversation = self.env['meta.conversation'].search([
                ('partner_id', '=', self.partner_id.id),
                ('state', 'in', ['new', 'open', 'pending'])
            ], limit=1, order='last_message_date desc')

        if not conversation:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No active conversation found for this customer.'),
                }
            }

        # Create message with order details
        lines_text = []
        for line in self.order_line:
            lines_text.append(f"- {line.product_id.name} x {line.product_uom_qty} = {self.currency_id.symbol}{line.price_subtotal:,.2f}")

        body = f"""
        <p><strong>{_('Order')} {self.name}</strong></p>
        <p>{_('Products')}:</p>
        <p>{'<br/>'.join(lines_text)}</p>
        <p><strong>{_('Total')}: {self.currency_id.symbol}{self.amount_total:,.2f}</strong></p>
        """

        message = self.env['meta.message'].create({
            'conversation_id': conversation.id,
            'message_type': 'outbound',
            'body': body,
            'state': 'draft',
        })

        # Send the message
        try:
            message.action_send()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _('Quotation sent successfully!'),
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'danger',
                    'message': _('Failed to send: %s') % str(e),
                }
            }

    def action_send_products_via_meta(self):
        """Open wizard to send products from this order via Meta"""
        self.ensure_one()

        conversation = self.meta_conversation_id
        if not conversation and self.partner_id:
            conversation = self.env['meta.conversation'].search([
                ('partner_id', '=', self.partner_id.id),
                ('state', 'in', ['new', 'open', 'pending'])
            ], limit=1, order='last_message_date desc')

        if not conversation:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('No active conversation found for this customer.'),
                }
            }

        product_ids = self.order_line.mapped('product_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Products'),
            'res_model': 'meta.send.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_conversation_id': conversation.id,
                'default_product_ids': [(6, 0, product_ids)],
            },
        }
