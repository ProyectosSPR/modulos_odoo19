# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MetaConversationTag(models.Model):
    """Tags for categorizing conversations"""
    _name = 'meta.conversation.tag'
    _description = 'Conversation Tag'
    _order = 'name'

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag name already exists!'),
    ]
