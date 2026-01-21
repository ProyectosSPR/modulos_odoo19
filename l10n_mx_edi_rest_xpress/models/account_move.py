# -*- coding: utf-8 -*-

from odoo import _, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_cfdi_invoice_document_cancel_failed(self, error, cfdi, cancel_reason):
        """
        Override to post error message to chatter when cancellation fails.
        This makes errors visible to the user in the invoice's chatter.
        """
        # Call parent method first
        result = super()._l10n_mx_edi_cfdi_invoice_document_cancel_failed(error, cfdi, cancel_reason)

        # Post error to chatter so user can see it
        self.message_post(
            body=_("Error al cancelar CFDI: %s", error),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        return result

    def _l10n_mx_edi_cfdi_invoice_document_cancel_requested_failed(self, error, cfdi, cancel_reason):
        """
        Override to post error message to chatter when cancel request fails (production mode).
        """
        # Call parent method first
        result = super()._l10n_mx_edi_cfdi_invoice_document_cancel_requested_failed(error, cfdi, cancel_reason)

        # Post error to chatter so user can see it
        self.message_post(
            body=_("Error al solicitar cancelación de CFDI: %s", error),
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

        return result
