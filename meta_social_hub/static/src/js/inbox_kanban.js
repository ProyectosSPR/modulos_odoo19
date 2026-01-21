/** @odoo-module **/

import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

/**
 * Custom Kanban Controller for Meta Inbox
 * Adds real-time updates and quick actions
 */
class MetaInboxKanbanController extends KanbanController {
    setup() {
        super.setup();
        // Could add WebSocket connection here for real-time updates
    }

    /**
     * Refresh the view periodically for new messages
     */
    async onWillStart() {
        await super.onWillStart();
        // Auto-refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            if (document.visibilityState === 'visible') {
                this.model.root.load();
            }
        }, 30000);
    }

    /**
     * Clean up interval on destroy
     */
    onWillUnmount() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

/**
 * Custom Kanban Renderer for Meta Inbox
 */
class MetaInboxKanbanRenderer extends KanbanRenderer {
    /**
     * Add custom classes based on record data
     */
    getRecordClasses(record) {
        const classes = super.getRecordClasses(record);

        // Add unread class
        if (record.data.unread_count > 0) {
            classes.push('o_meta_unread');
        }

        // Add channel type class
        if (record.data.channel_type) {
            classes.push(`o_meta_channel_${record.data.channel_type}`);
        }

        return classes;
    }
}

// Register the custom inbox kanban view
const metaInboxKanbanView = {
    ...kanbanView,
    Controller: MetaInboxKanbanController,
    Renderer: MetaInboxKanbanRenderer,
};

registry.category("views").add("meta_inbox_kanban", metaInboxKanbanView);
