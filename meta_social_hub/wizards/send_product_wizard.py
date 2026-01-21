# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SendProductWizard(models.TransientModel):
    """Wizard to send product information via Meta channels"""
    _name = 'meta.send.product.wizard'
    _description = 'Send Product via Meta'

    conversation_id = fields.Many2one(
        'meta.conversation',
        string='Conversation',
        required=True
    )
    channel_type = fields.Selection(
        related='conversation_id.channel_type'
    )

    product_ids = fields.Many2many(
        'product.product',
        'meta_send_product_wizard_product_rel',
        'wizard_id',
        'product_id',
        string='Products',
        required=True
    )

    message = fields.Text(
        string='Additional Message',
        help='Optional message to include with the products'
    )

    include_price = fields.Boolean(
        string='Include Price',
        default=True
    )
    include_image = fields.Boolean(
        string='Include Image',
        default=True,
        help='Note: Images are sent as separate attachments on some platforms'
    )
    include_description = fields.Boolean(
        string='Include Description',
        default=True
    )
    include_link = fields.Boolean(
        string='Include Website Link',
        default=False,
        help='Include link to product page (requires website_sale)'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    preview = fields.Html(
        string='Preview',
        compute='_compute_preview'
    )

    @api.depends('product_ids', 'message', 'include_price', 'include_description', 'currency_id')
    def _compute_preview(self):
        for wizard in self:
            wizard.preview = wizard._format_message_body()

    def _format_message_body(self):
        """Format the message body with product information"""
        if not self.product_ids:
            return ''

        lines = []

        # Add custom message first
        if self.message:
            lines.append(Markup('<p>%s</p>') % self.message)

        lines.append(Markup('<p><strong>%s</strong></p>') % _('Products:'))

        for product in self.product_ids:
            product_lines = []

            # Product name and code
            name_line = f"<strong>{product.name}</strong>"
            if product.default_code:
                name_line += f" <em>[{product.default_code}]</em>"
            product_lines.append(name_line)

            # Price
            if self.include_price and product.lst_price:
                price_formatted = f"{self.currency_id.symbol}{product.lst_price:,.2f}"
                product_lines.append(f"💰 {_('Price')}: {price_formatted}")

            # Description
            if self.include_description and product.description_sale:
                desc = product.description_sale[:200]
                if len(product.description_sale) > 200:
                    desc += '...'
                product_lines.append(f"📝 {desc}")

            # Website link
            if self.include_link:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                if product.website_url:
                    link = f"{base_url}{product.website_url}"
                    product_lines.append(f"🔗 <a href='{link}'>{_('View Product')}</a>")

            lines.append(Markup('<p>%s</p>') % Markup('<br/>').join(product_lines))

        return Markup('').join(lines)

    def action_send(self):
        """Send the products via the conversation channel"""
        self.ensure_one()

        if not self.product_ids:
            raise UserError(_('Please select at least one product.'))

        # Create message
        body = self._format_message_body()

        message_vals = {
            'conversation_id': self.conversation_id.id,
            'message_type': 'outbound',
            'body': body,
            'product_ids': [(6, 0, self.product_ids.ids)],
            'state': 'draft',
        }

        # Add product images as attachments if requested
        if self.include_image:
            attachment_ids = []
            for product in self.product_ids:
                if product.image_1920:
                    attachment = self.env['ir.attachment'].create({
                        'name': f"{product.name}.jpg",
                        'datas': product.image_1920,
                        'mimetype': 'image/jpeg',
                    })
                    attachment_ids.append(attachment.id)

            if attachment_ids:
                message_vals['attachment_ids'] = [(6, 0, attachment_ids)]

        message = self.env['meta.message'].create(message_vals)

        # Send the message
        try:
            message.action_send()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _('Products sent successfully!'),
                    'next': {'type': 'ir.actions.act_window_close'},
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

    def action_preview(self):
        """Just refresh the preview"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'meta.send.product.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
