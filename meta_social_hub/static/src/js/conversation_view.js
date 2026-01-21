/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";

/**
 * Conversation Messages Component
 * Displays messages in a chat-like interface
 */
export class MetaConversationMessages extends Component {
    static template = "meta_social_hub.ConversationMessages";
    static props = {
        conversationId: { type: Number },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            messages: [],
            loading: true,
            hasMore: false,
            offset: 0,
        });

        onWillStart(async () => {
            await this.loadMessages();
        });

        onMounted(() => {
            this.scrollToBottom();
        });
    }

    async loadMessages() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                "meta.message",
                "search_read",
                [[["conversation_id", "=", this.props.conversationId]]],
                {
                    fields: ["body", "message_type", "state", "create_date", "author_user_id", "attachment_ids"],
                    order: "create_date asc",
                    limit: 50,
                    offset: this.state.offset,
                }
            );
            this.state.messages = [...this.state.messages, ...result];
            this.state.hasMore = result.length === 50;
        } finally {
            this.state.loading = false;
        }
    }

    async loadMore() {
        this.state.offset += 50;
        await this.loadMessages();
    }

    scrollToBottom() {
        const container = this.el?.querySelector(".o_meta_messages_container");
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    getMessageClass(message) {
        const classes = ["o_meta_message"];
        if (message.message_type === "inbound") {
            classes.push("o_meta_message_inbound");
        } else {
            classes.push("o_meta_message_outbound");
        }
        return classes.join(" ");
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        const date = new Date(dateStr);
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
}

/**
 * Quick Actions Component
 */
export class MetaQuickActions extends Component {
    static template = "meta_social_hub.QuickActions";
    static props = {
        conversationId: { type: Number },
    };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async assignToMe() {
        await this.orm.call(
            "meta.conversation",
            "action_assign_to_me",
            [[this.props.conversationId]]
        );
        this.notification.add("Conversation assigned to you", { type: "success" });
    }

    async createLead() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Create Lead",
            res_model: "meta.create.lead.wizard",
            view_mode: "form",
            target: "new",
            context: {
                default_conversation_id: this.props.conversationId,
            },
        });
    }

    async createTicket() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Create Ticket",
            res_model: "meta.create.ticket.wizard",
            view_mode: "form",
            target: "new",
            context: {
                default_conversation_id: this.props.conversationId,
            },
        });
    }

    async sendProducts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Send Products",
            res_model: "meta.send.product.wizard",
            view_mode: "form",
            target: "new",
            context: {
                default_conversation_id: this.props.conversationId,
            },
        });
    }
}

// Register components
registry.category("components").add("MetaConversationMessages", MetaConversationMessages);
registry.category("components").add("MetaQuickActions", MetaQuickActions);
