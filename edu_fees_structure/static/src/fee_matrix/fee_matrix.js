/** @odoo-module */

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class FeeMatrixWidget extends Component {
    static template = "edu_fees_structure.FeeMatrixWidget";
    static props = {
        record: { type: Object },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            terms: [],
            feeHeads: [],
            amounts: {},
            currencySymbol: "",
            isReadonly: false,
            loading: true,
        });

        onWillStart(() => this.loadMatrix());
        onWillUpdateProps(() => this.loadMatrix());
    }

    get structureId() {
        return this.props.record.resId;
    }

    async loadMatrix() {
        const id = this.structureId;
        if (!id) {
            this.state.loading = false;
            return;
        }
        try {
            const data = await this.orm.call(
                "edu.fee.structure",
                "get_fee_matrix_data",
                [id]
            );
            this.state.terms = data.terms;
            this.state.feeHeads = data.fee_heads;
            this.state.amounts = data.amounts;
            this.state.currencySymbol = data.currency_symbol;
            this.state.isReadonly = data.readonly;
            this.state.loading = false;
        } catch {
            this.state.loading = false;
        }
    }

    getAmount(termId, headId) {
        const cell = this.state.amounts[`${termId}_${headId}`];
        return cell ? cell.amount : 0;
    }

    fmt(amount) {
        return amount.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    getRowTotal(termId) {
        return this.state.feeHeads.reduce(
            (s, h) => s + this.getAmount(termId, h.id),
            0
        );
    }

    getColTotal(headId) {
        return this.state.terms.reduce(
            (s, t) => s + this.getAmount(t.id, headId),
            0
        );
    }

    getGrandTotal() {
        return this.state.terms.reduce(
            (s, t) => s + this.getRowTotal(t.id),
            0
        );
    }

    async onCellChange(termId, headId, ev) {
        const value = parseFloat(ev.target.value) || 0;
        const key = `${termId}_${headId}`;
        if (!this.state.amounts[key]) {
            this.state.amounts[key] = { amount: value };
        } else {
            this.state.amounts[key].amount = value;
        }
        try {
            await this.orm.call(
                "edu.fee.structure",
                "save_fee_matrix_cell",
                [this.structureId, termId, headId, value]
            );
        } catch (e) {
            this.notification.add("Failed to save amount", { type: "danger" });
        }
    }

    async onRefresh() {
        this.state.loading = true;
        await this.loadMatrix();
    }

    get editable() {
        return !this.state.isReadonly && !this.props.readonly;
    }
}

const feeMatrixWidgetDef = { component: FeeMatrixWidget };
registry.category("view_widgets").add("fee_matrix", feeMatrixWidgetDef);
