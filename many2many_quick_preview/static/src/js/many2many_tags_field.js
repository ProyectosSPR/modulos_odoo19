/** @odoo-module **/

import { Many2ManyTagsFieldColorEditable } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { patch } from "@web/core/utils/patch";

patch(Many2ManyTagsFieldColorEditable.prototype, {
    onTagClick(ev, record) {
        const onTagClick = super.onTagClick(ev, record);
        var action = {
            type: 'ir.actions.act_window',
            res_model: record.resModel,
            res_id: record.resId,
            views: [[false, 'form']],
            target: 'new',
        };
        this.env.model.action.doAction(action);
        return onTagClick;
    }
});