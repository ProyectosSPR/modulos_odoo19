# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hmac
import hashlib
import json
import logging
import requests
from markupsafe import Markup

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MessengerWebhookController(http.Controller):
    """
    Webhook controller for Facebook Messenger.

    Facebook sends events to this endpoint when:
    - Messages are received
    - Messages are delivered/read
    - Postback buttons are clicked
    - etc.

    Setup required:
    1. Create a Facebook App at developers.facebook.com
    2. Add Messenger Platform product
    3. Configure webhook URL to: https://your-domain.com/meta/messenger/webhook
    4. Set verify token in Odoo settings
    5. Subscribe to page events
    """

    @http.route('/meta/messenger/webhook', type='http', auth='public',
                methods=['GET'], csrf=False)
    def messenger_webhook_verify(self, **kwargs):
        """
        Webhook verification endpoint.
        Facebook sends a GET request to verify the webhook URL.
        """
        mode = kwargs.get('hub.mode')
        token = kwargs.get('hub.verify_token')
        challenge = kwargs.get('hub.challenge')

        # Get verify token from settings
        verify_token = request.env['ir.config_parameter'].sudo().get_param(
            'meta_social_hub.messenger_verify_token', ''
        )

        if mode == 'subscribe' and token == verify_token:
            _logger.info('Messenger webhook verified successfully')
            return challenge
        else:
            _logger.warning('Messenger webhook verification failed. Token mismatch.')
            return 'Verification failed', 403

    @http.route('/meta/messenger/webhook', type='json', auth='public',
                methods=['POST'], csrf=False)
    def messenger_webhook_event(self, **kwargs):
        """
        Webhook event handler.
        Receives events from Facebook Messenger.
        """
        try:
            data = request.get_json_data()
        except Exception:
            data = json.loads(request.httprequest.data.decode('utf-8'))

        _logger.debug('Messenger webhook received: %s', json.dumps(data, indent=2))

        # Verify signature (optional but recommended)
        if not self._verify_signature():
            _logger.warning('Invalid webhook signature')
            # Continue processing anyway for development
            # In production, you might want to reject

        object_type = data.get('object')

        if object_type == 'page':
            # Process page events
            for entry in data.get('entry', []):
                page_id = entry.get('id')

                # Process messaging events
                for messaging in entry.get('messaging', []):
                    self._process_messaging_event(page_id, messaging)

                # Process standby events (for handover protocol)
                for standby in entry.get('standby', []):
                    self._process_standby_event(page_id, standby)

        elif object_type == 'instagram':
            # Process Instagram events
            for entry in data.get('entry', []):
                ig_id = entry.get('id')

                for messaging in entry.get('messaging', []):
                    self._process_instagram_event(ig_id, messaging)

        return 'ok'

    def _verify_signature(self):
        """
        Verify the X-Hub-Signature-256 header.
        """
        signature = request.httprequest.headers.get('X-Hub-Signature-256', '')
        if not signature:
            return True  # No signature to verify

        app_secret = request.env['ir.config_parameter'].sudo().get_param(
            'social.facebook_client_secret', ''
        )
        if not app_secret:
            return True  # No secret configured

        # Compute expected signature
        payload = request.httprequest.data
        expected = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def _process_messaging_event(self, page_id, messaging):
        """
        Process a Messenger messaging event.
        """
        sender_id = messaging.get('sender', {}).get('id')
        recipient_id = messaging.get('recipient', {}).get('id')
        timestamp = messaging.get('timestamp')

        # Skip if sender is the page itself (echo of our own messages)
        if sender_id == page_id:
            return

        # Find the meta channel for this page
        channel = request.env['meta.channel'].sudo().search([
            ('channel_type', '=', 'facebook_messenger'),
            ('facebook_page_id', '=', page_id),
        ], limit=1)

        if not channel:
            _logger.warning('No meta channel found for page %s', page_id)
            return

        if messaging.get('message'):
            self._handle_message(channel, sender_id, messaging['message'], timestamp)
        elif messaging.get('postback'):
            self._handle_postback(channel, sender_id, messaging['postback'], timestamp)
        elif messaging.get('delivery'):
            self._handle_delivery(channel, sender_id, messaging['delivery'])
        elif messaging.get('read'):
            self._handle_read(channel, sender_id, messaging['read'])

    def _handle_message(self, channel, sender_id, message_data, timestamp):
        """
        Handle incoming message.
        """
        message_id = message_data.get('mid')
        text = message_data.get('text', '')
        attachments = message_data.get('attachments', [])
        reply_to = message_data.get('reply_to', {}).get('mid')

        # Get sender info from Facebook
        sender_info = self._get_sender_info(channel, sender_id)
        sender_name = sender_info.get('name', sender_id)
        sender_avatar = sender_info.get('avatar')

        # Find or create conversation
        MetaConversation = request.env['meta.conversation'].sudo()
        conversation = MetaConversation.get_or_create_conversation(
            channel_id=channel.id,
            external_id=sender_id,
            external_name=sender_name,
            avatar=sender_avatar
        )

        # Process attachments
        attachment_records = []
        for att in attachments:
            att_type = att.get('type')  # image, video, audio, file, location
            payload = att.get('payload', {})

            if att_type in ['image', 'video', 'audio', 'file']:
                url = payload.get('url')
                if url:
                    # Download and create attachment
                    attachment = self._download_attachment(url, att_type)
                    if attachment:
                        attachment_records.append(attachment)
            elif att_type == 'location':
                # Handle location
                lat = payload.get('coordinates', {}).get('lat')
                lng = payload.get('coordinates', {}).get('long')
                if lat and lng:
                    text += f"\n📍 Location: {lat}, {lng}"

        # Create meta message
        MetaMessage = request.env['meta.message'].sudo()
        message = MetaMessage.create_from_webhook(
            conversation=conversation,
            external_id=message_id,
            body=text,
            message_type='inbound',
            attachments=[{'id': a.id, 'name': a.name} for a in attachment_records] if attachment_records else None,
            reply_to_external_id=reply_to
        )

        if attachment_records:
            message.write({'attachment_ids': [(6, 0, [a.id for a in attachment_records])]})

        _logger.info('Created message %s in conversation %s', message.id, conversation.id)

    def _handle_postback(self, channel, sender_id, postback_data, timestamp):
        """
        Handle postback events (button clicks, quick replies).
        """
        payload = postback_data.get('payload', '')
        title = postback_data.get('title', '')

        # Find conversation
        MetaConversation = request.env['meta.conversation'].sudo()
        conversation = MetaConversation.search([
            ('channel_id', '=', channel.id),
            ('external_id', '=', sender_id),
        ], limit=1)

        if not conversation:
            return

        # Create message representing the postback
        body = f"[Button Click] {title}: {payload}"
        MetaMessage = request.env['meta.message'].sudo()
        MetaMessage.create_from_webhook(
            conversation=conversation,
            external_id=f"postback_{timestamp}",
            body=body,
            message_type='inbound'
        )

    def _handle_delivery(self, channel, sender_id, delivery_data):
        """
        Handle delivery receipts.
        """
        message_ids = delivery_data.get('mids', [])

        for mid in message_ids:
            message = request.env['meta.message'].sudo().search([
                ('external_id', '=', mid),
                ('message_type', '=', 'outbound'),
            ], limit=1)

            if message:
                message.update_status('delivered')

    def _handle_read(self, channel, sender_id, read_data):
        """
        Handle read receipts.
        """
        watermark = read_data.get('watermark')  # Timestamp, all messages before this are read

        if watermark:
            # Mark all messages before watermark as read
            messages = request.env['meta.message'].sudo().search([
                ('conversation_id.channel_id', '=', channel.id),
                ('conversation_id.external_id', '=', sender_id),
                ('message_type', '=', 'outbound'),
                ('state', '!=', 'read'),
            ])

            for message in messages:
                if message.sent_date and message.sent_date.timestamp() * 1000 <= watermark:
                    message.update_status('read')

    def _get_sender_info(self, channel, sender_id):
        """
        Get sender profile info from Facebook Graph API.
        """
        if not channel.facebook_access_token:
            return {}

        try:
            endpoint = request.env['social.media']._FACEBOOK_ENDPOINT_VERSIONED
            url = f"{endpoint}/{sender_id}"

            response = requests.get(url, params={
                'fields': 'name,profile_pic',
                'access_token': channel.facebook_access_token
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                result = {'name': data.get('name')}

                # Download profile pic
                pic_url = data.get('profile_pic')
                if pic_url:
                    try:
                        pic_response = requests.get(pic_url, timeout=10)
                        if pic_response.status_code == 200:
                            import base64
                            result['avatar'] = base64.b64encode(pic_response.content)
                    except Exception:
                        pass

                return result
        except Exception as e:
            _logger.warning('Failed to get sender info: %s', e)

        return {}

    def _download_attachment(self, url, att_type):
        """
        Download attachment from Facebook CDN.
        """
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                import base64
                import mimetypes

                # Guess filename and mimetype
                content_type = response.headers.get('Content-Type', 'application/octet-stream')
                ext = mimetypes.guess_extension(content_type) or ''
                filename = f"{att_type}{ext}"

                return request.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'datas': base64.b64encode(response.content),
                    'mimetype': content_type,
                })
        except Exception as e:
            _logger.warning('Failed to download attachment: %s', e)

        return None

    def _process_standby_event(self, page_id, standby):
        """
        Handle standby events (Handover Protocol).
        Used when your app is in standby mode and another app has thread control.
        """
        # This is for advanced handover scenarios
        pass

    def _process_instagram_event(self, ig_id, messaging):
        """
        Process Instagram DM events.
        Similar to Messenger but for Instagram accounts.
        """
        sender_id = messaging.get('sender', {}).get('id')
        recipient_id = messaging.get('recipient', {}).get('id')

        # Find the meta channel for this Instagram account
        channel = request.env['meta.channel'].sudo().search([
            ('channel_type', '=', 'instagram'),
            ('instagram_account_id', '=', ig_id),
        ], limit=1)

        if not channel:
            _logger.warning('No meta channel found for Instagram %s', ig_id)
            return

        if messaging.get('message'):
            self._handle_instagram_message(channel, sender_id, messaging['message'])

    def _handle_instagram_message(self, channel, sender_id, message_data):
        """
        Handle incoming Instagram DM.
        """
        message_id = message_data.get('mid')
        text = message_data.get('text', '')
        attachments = message_data.get('attachments', [])

        # Find or create conversation
        MetaConversation = request.env['meta.conversation'].sudo()
        conversation = MetaConversation.get_or_create_conversation(
            channel_id=channel.id,
            external_id=sender_id,
            external_name=sender_id  # Instagram doesn't provide name in webhook
        )

        # Create meta message
        MetaMessage = request.env['meta.message'].sudo()
        MetaMessage.create_from_webhook(
            conversation=conversation,
            external_id=message_id,
            body=text,
            message_type='inbound'
        )
