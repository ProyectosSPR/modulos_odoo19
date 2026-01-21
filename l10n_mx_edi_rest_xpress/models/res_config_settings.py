# -*- coding: utf-8 -*-

from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_rest_xpress_check_credits(self):
        """
        Proxy method to call company's check credits action from settings.
        """
        return self.company_id.action_rest_xpress_check_credits()
