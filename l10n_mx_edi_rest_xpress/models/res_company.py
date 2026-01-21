# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_pac = fields.Selection(
        selection_add=[
            ('rest_xpress', 'REST XPRESS (Timbrador Xpress)')
        ],
        ondelete={'rest_xpress': 'set default'}
    )

    def _l10n_mx_edi_get_pac_credentials(self):
        """
        Extend to add REST XPRESS credentials.

        For REST XPRESS, we use:
        - l10n_mx_edi_pac_password: API Key (not a username/password)
        - l10n_mx_edi_pac_test_env: Test mode flag

        Returns a dict with the PAC credentials.
        """
        self.ensure_one()

        if self.l10n_mx_edi_pac == 'rest_xpress':
            # REST XPRESS uses API Key authentication
            base_url = 'https://dev.timbradorxpress.mx' if self.l10n_mx_edi_pac_test_env else 'https://app.timbradorxpress.mx'
            return {
                'api_key': self.l10n_mx_edi_pac_password,
                'sign_url': f'{base_url}/api/rest/servicio/timbrarJSON',
                'cancel_url': f'{base_url}/api/rest/servicio/cancelarPEM',
                'status_url': f'{base_url}/api/rest/servicio/consultarEstadoSAT',
                'credits_url': f'{base_url}/api/rest/servicio/consultarCreditosDisponibles',
                'test_mode': self.l10n_mx_edi_pac_test_env,
            }

        # Call parent for other PACs
        return super()._l10n_mx_edi_get_pac_credentials()

    def action_rest_xpress_check_credits(self):
        """
        Action to check available credits (timbres) in REST XPRESS account.
        Called from configuration view.
        """
        self.ensure_one()

        if self.l10n_mx_edi_pac != 'rest_xpress':
            raise UserError(_('Esta acción solo está disponible para el PAC REST XPRESS.'))

        if not self.l10n_mx_edi_pac_password:
            raise UserError(_('Por favor configure la API Key de REST XPRESS primero.'))

        # Get credentials
        credentials = self._l10n_mx_edi_get_pac_credentials()

        # Query credits using the document model method
        edi_document = self.env['l10n_mx_edi.document']
        result = edi_document._rest_xpress_get_credits(credentials)

        if result.get('success'):
            credits = result.get('credits', 0)
            env_text = 'Desarrollo' if self.l10n_mx_edi_pac_test_env else 'Producción'
            message = _(
                'REST XPRESS - Créditos Disponibles\n\n'
                'Ambiente: %(env)s\n'
                'Timbres disponibles: %(credits)s',
                env=env_text,
                credits=credits
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Créditos REST XPRESS'),
                    'message': _('Timbres disponibles: %s (%s)') % (credits, env_text),
                    'type': 'success',
                    'sticky': True,
                }
            }
        else:
            errors = result.get('errors', [_('Error desconocido')])
            raise UserError('\n'.join(errors))
