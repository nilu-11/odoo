/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { Activity } from "@mail/core/common/activity_model";

/**
 * Reload crm.lead form when activities change.
 *
 * Two patches work together:
 * 1. Activity model patch: after mark-done / delete, posts a message
 *    on a BroadcastChannel to signal the form.
 * 2. FormController patch: listens for that signal and reloads the
 *    record so the inline activity_ids and interaction_log_ids lists
 *    refresh without a manual page reload.
 */

const CHANNEL_NAME = "edu_pre_admission_activity_reload";

// ── FormController: listen for reload signals ──────────────────────
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this._eduActivityChannel = new BroadcastChannel(CHANNEL_NAME);
        this._eduActivityChannel.onmessage = async (ev) => {
            if (
                ev.data?.type === "RELOAD_FORM" &&
                this.model.root?.resModel === "crm.lead" &&
                this.model.root?.resId === ev.data?.payload?.id
            ) {
                await this.model.root.load();
                this.render(true);
            }
        };
    },

    /**
     * After any object-type button action on crm.lead, reload.
     * Handles our custom Schedule/Log Interaction buttons.
     */
    async onButtonClicked(params) {
        const result = await super.onButtonClicked(...arguments);
        if (this.model.root?.resModel === "crm.lead") {
            await this.model.root.load();
            this.render(true);
        }
        return result;
    },
});

// ── Activity model: signal form reload after changes ───────────────
patch(Activity.prototype, {
    async markAsDone(attachmentIds = []) {
        const resId = this.res_id;
        const resModel = this.res_model;
        await super.markAsDone(...arguments);
        if (resModel === "crm.lead") {
            new BroadcastChannel(CHANNEL_NAME).postMessage({
                type: "RELOAD_FORM",
                payload: { id: resId, model: resModel },
            });
        }
    },

    async markAsDoneAndScheduleNext() {
        const resId = this.res_id;
        const resModel = this.res_model;
        const result = await super.markAsDoneAndScheduleNext(...arguments);
        if (resModel === "crm.lead") {
            new BroadcastChannel(CHANNEL_NAME).postMessage({
                type: "RELOAD_FORM",
                payload: { id: resId, model: resModel },
            });
        }
        return result;
    },

    remove({ broadcast = true } = {}) {
        const resId = this.res_id;
        const resModel = this.res_model;
        super.remove(...arguments);
        if (resModel === "crm.lead" && broadcast) {
            new BroadcastChannel(CHANNEL_NAME).postMessage({
                type: "RELOAD_FORM",
                payload: { id: resId, model: resModel },
            });
        }
    },
});
