/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

class TtsAudioPlayer extends Component {
    static template = "nepali_tts.TtsAudioPlayer";
    static props = { ...standardWidgetProps };

    setup() {
        this.notification = useService("notification");
        this.state = useState({ loading: false, audioUrl: null });
        this.audioRef = useRef("audio");
    }

    get record() {
        return this.props.record;
    }

    get currentUrl() {
        const attachment = this.record.data.audio_attachment_id;
        if (attachment && attachment[0]) {
            return `/web/content/${attachment[0]}?download=false`;
        }
        return null;
    }

    async onGenerate() {
        if (this.state.loading) return;
        this.state.loading = true;
        try {
            if (this.record.isDirty || !this.record.resId) {
                await this.record.save();
            }
            const result = await rpc("/nepali_tts/generate", {
                record_id: this.record.resId,
            });
            if (result && result.error) {
                this.notification.add(result.error, { type: "danger" });
            } else if (result && result.url) {
                this.state.audioUrl = result.url;
                await this.record.load();
                // autoplay after OWL re-renders
                setTimeout(() => {
                    if (this.audioRef.el) {
                        this.audioRef.el.play().catch(() => {});
                    }
                }, 100);
            }
        } catch (e) {
            this.notification.add("Network error. Please try again.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("view_widgets").add("tts_audio_player", {
    component: TtsAudioPlayer,
});
