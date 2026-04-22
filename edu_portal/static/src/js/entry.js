/**
 * Kopila EMIS Portal — data-entry helpers
 * Attendance status buttons, photo grid, marks input,
 * attendance modal, view switcher, matrix date filter.
 *
 * Depends on: portal.js (kopila namespace, kopila.toast, kopila.icon)
 * No React, no build step.
 */
(function () {
    "use strict";

    var kopila = window.kopila = window.kopila || {};

    function qs(sel, root) { return (root || document).querySelector(sel); }
    function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

    /* ------------------------------------------------------------------ */
    /*  Helpers                                                           */
    /* ------------------------------------------------------------------ */
    var STATUS_CYCLE = ["p", "a", "l", "e", null];
    var STATUS_LABELS = { p: "Present", a: "Absent", l: "Late", e: "Excused" };
    var STATUS_COLORS = { p: "success", a: "danger", l: "warn", e: "info" };
    var STATUS_KEYS   = { p: "p", a: "a", l: "l", e: "e" };

    /**
     * Update live attendance counters on the page.
     * Looks for elements: #att-count-present, #att-count-absent, etc.
     */
    function updateCounters() {
        var rows = qsa("[data-att-status]");
        var counts = { p: 0, a: 0, l: 0, e: 0, unmarked: 0 };
        rows.forEach(function (row) {
            var s = row.getAttribute("data-att-status");
            if (s && counts.hasOwnProperty(s)) {
                counts[s]++;
            } else {
                counts.unmarked++;
            }
        });

        var total = rows.length || 1;

        var map = {
            "#att-count-present":  counts.p,
            "#att-count-absent":   counts.a,
            "#att-count-late":     counts.l,
            "#att-count-excused":  counts.e,
            "#att-count-unmarked": counts.unmarked
        };
        for (var sel in map) {
            var el = qs(sel);
            if (el) el.textContent = map[sel];
        }

        /* Update percentage bars if they exist */
        var barMap = {
            "#att-bar-present":  counts.p,
            "#att-bar-absent":   counts.a,
            "#att-bar-late":     counts.l,
            "#att-bar-excused":  counts.e,
            "#att-bar-unmarked": counts.unmarked
        };
        for (var bsel in barMap) {
            var bar = qs(bsel);
            if (bar) bar.style.width = ((barMap[bsel] / total) * 100) + "%";
        }
    }

    /**
     * Apply a status to a single student row or card.
     * @param {Element} rowEl - the DOM element with data-student-id
     * @param {string|null} status - "p","a","l","e", or null to clear
     */
    function applyStatus(rowEl, status) {
        if (!rowEl) return;

        /* Update data attribute */
        if (status) {
            rowEl.setAttribute("data-att-status", status);
        } else {
            rowEl.removeAttribute("data-att-status");
        }

        /* Update button states inside the row */
        qsa(".att-btn", rowEl).forEach(function (btn) {
            var btnStatus = btn.getAttribute("data-status");
            var isActive = btnStatus === status;
            btn.classList.toggle("active", isActive);
            var color = STATUS_COLORS[btnStatus] || "";
            if (isActive && color) {
                btn.classList.add("att-btn--" + color);
            } else {
                btn.classList.remove("att-btn--success", "att-btn--danger", "att-btn--warn", "att-btn--info");
                if (isActive && color) {
                    btn.classList.add("att-btn--" + color);
                }
            }
        });

        /* Update row background tint */
        rowEl.classList.remove("att-row--p", "att-row--a", "att-row--l", "att-row--e");
        if (status) {
            rowEl.classList.add("att-row--" + status);
        }

        updateCounters();
    }

    /* ------------------------------------------------------------------ */
    /*  1. Attendance Status Buttons                                      */
    /* ------------------------------------------------------------------ */
    function initAttendanceButtons() {
        document.addEventListener("click", function (e) {
            var btn = e.target.closest(".att-btn");
            if (!btn) return;

            var row = btn.closest("[data-student-id]");
            if (!row) return;

            var status = btn.getAttribute("data-status");
            var current = row.getAttribute("data-att-status");

            /* Toggle off if clicking same status */
            var newStatus = (current === status) ? null : status;
            applyStatus(row, newStatus);

            /* Fire HTMX if data-hx-post is set on the button */
            if (btn.hasAttribute("hx-post") || btn.hasAttribute("data-hx-post")) {
                /* Let HTMX handle it; we just update the UI optimistically */
                return;
            }

            /* Manual AJAX — find URL and sheet_id from roster container */
            var container = row.closest("[data-mark-url]");
            var postUrl = row.getAttribute("data-att-url")
                || (container ? container.getAttribute("data-mark-url") : null);
            if (postUrl && newStatus) {
                var studentId = row.getAttribute("data-student-id");
                var sheetId = container ? container.getAttribute("data-sheet-id") : "";
                var csrf = qs('input[name="csrf_token"]');
                var body = new FormData();
                body.append("student_id", studentId);
                body.append("status", newStatus);
                if (sheetId) body.append("sheet_id", sheetId);
                if (csrf) body.append("csrf_token", csrf.value);

                fetch(postUrl, {
                    method: "POST",
                    body: body,
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                }).then(function (resp) {
                    if (!resp.ok) {
                        kopila.toast("Failed to save — try again");
                    }
                }).catch(function () {
                    kopila.toast("Network error — check your connection");
                });
            }
        });

        /* Keyboard shortcuts: P/A/L/E when a student row is focused */
        document.addEventListener("keydown", function (e) {
            /* Skip if typing in an input field */
            var tag = (e.target.tagName || "").toLowerCase();
            if (tag === "input" || tag === "textarea" || tag === "select") return;
            if (e.target.isContentEditable) return;

            var key = e.key.toLowerCase();
            if (!STATUS_KEYS.hasOwnProperty(key)) return;

            /* Find the focused/active student row */
            var row = e.target.closest("[data-student-id]");
            if (!row) {
                /* Try the row that has focus outline */
                row = qs("[data-student-id]:focus, [data-student-id].focused");
            }
            if (!row) return;

            e.preventDefault();
            var current = row.getAttribute("data-att-status");
            var newStatus = (current === key) ? null : key;
            applyStatus(row, newStatus);

            /* Advance to next row */
            var next = row.nextElementSibling;
            if (next && next.hasAttribute("data-student-id")) {
                next.setAttribute("tabindex", "0");
                next.focus();
            }
        });

        /* Tab navigation between student rows */
        qsa("[data-student-id]").forEach(function (row) {
            row.setAttribute("tabindex", "0");
        });

        /* "Mark All Present" button */
        document.addEventListener("click", function (e) {
            var btn = e.target.closest(".att-mark-all-present, [data-action='mark-all-present']");
            if (!btn) return;
            e.preventDefault();

            var rows = qsa("[data-student-id]");
            var count = 0;
            rows.forEach(function (row) {
                applyStatus(row, "p");
                count++;
            });
            updateCounters();
            kopila.toast("Marked all " + count + " students present");

            /* Post bulk action if URL is available */
            var bulkUrl = btn.getAttribute("data-url") || btn.getAttribute("hx-post");
            if (bulkUrl && !btn.hasAttribute("hx-post")) {
                var csrf = qs('input[name="csrf_token"]');
                var body = new FormData();
                body.append("action", "mark_all_present");
                if (csrf) body.append("csrf_token", csrf.value);
                fetch(bulkUrl, {
                    method: "POST",
                    body: body,
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                });
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  2. Attendance Photo Grid                                          */
    /* ------------------------------------------------------------------ */
    function initPhotoGrid() {
        document.addEventListener("click", function (e) {
            var card = e.target.closest(".att-photo-card");
            if (!card) return;

            e.preventDefault();
            var current = card.getAttribute("data-att-status") || null;
            var idx = STATUS_CYCLE.indexOf(current);
            var next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];

            applyStatus(card, next);

            /* Visual: update border color */
            card.classList.remove("border-success", "border-danger", "border-warn", "border-info", "border-default");
            if (next && STATUS_COLORS[next]) {
                card.classList.add("border-" + STATUS_COLORS[next]);
            } else {
                card.classList.add("border-default");
            }

            /* Update status badge on photo */
            var badge = qs(".att-photo-badge", card);
            if (badge) {
                if (next) {
                    badge.textContent = next.toUpperCase();
                    badge.className = "att-photo-badge att-photo-badge--" + STATUS_COLORS[next];
                    badge.style.display = "";
                } else {
                    badge.style.display = "none";
                }
            }

            /* AJAX save */
            var container = card.closest("[data-mark-url]");
            var postUrl = container ? container.getAttribute("data-mark-url") : null;
            if (postUrl && next) {
                var studentId = card.getAttribute("data-student-id");
                var sheetId = container ? container.getAttribute("data-sheet-id") : "";
                var csrf = qs('input[name="csrf_token"]');
                var body = new FormData();
                body.append("student_id", studentId);
                body.append("status", next);
                if (sheetId) body.append("sheet_id", sheetId);
                if (csrf) body.append("csrf_token", csrf.value);

                fetch(postUrl, {
                    method: "POST",
                    body: body,
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                }).then(function (resp) {
                    if (!resp.ok) kopila.toast("Failed to save");
                }).catch(function () {
                    kopila.toast("Network error");
                });
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  3. Marks Input                                                    */
    /* ------------------------------------------------------------------ */
    function initMarksInput() {
        /* Enter key moves to next marks input field */
        document.addEventListener("keydown", function (e) {
            if (e.key !== "Enter" && e.key !== "Tab") return;

            var input = e.target;
            if (!input.classList.contains("marks-input")) return;

            /* For Enter, move to next input (Tab is handled natively) */
            if (e.key === "Enter") {
                e.preventDefault();

                var all = qsa(".marks-input");
                var idx = all.indexOf(input);
                if (idx >= 0 && idx < all.length - 1) {
                    all[idx + 1].focus();
                    all[idx + 1].select();
                } else if (idx === all.length - 1) {
                    /* Last field — blur to trigger any validation */
                    input.blur();
                }
            }
        });

        /* Auto-validate marks on blur */
        document.addEventListener("change", function (e) {
            var input = e.target;
            if (!input.classList.contains("marks-input")) return;

            var val = parseFloat(input.value);
            var max = parseFloat(input.getAttribute("data-max") || input.getAttribute("max") || "100");
            var min = parseFloat(input.getAttribute("data-min") || input.getAttribute("min") || "0");

            if (isNaN(val)) return;

            if (val > max) {
                input.value = max;
                kopila.toast("Maximum marks: " + max);
            } else if (val < min) {
                input.value = min;
                kopila.toast("Minimum marks: " + min);
            }

            /* Update visual feedback */
            input.classList.remove("marks-input--high", "marks-input--low", "marks-input--fail");
            if (!isNaN(val)) {
                var pct = (val / max) * 100;
                if (pct >= 80) {
                    input.classList.add("marks-input--high");
                } else if (pct < 40) {
                    input.classList.add("marks-input--fail");
                }
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  4. Attendance Modal                                               */
    /* ------------------------------------------------------------------ */
    var activeModal = null;

    /**
     * Open an attendance modal by selector or element.
     * @param {string|Element} sel
     */
    kopila.openAttendanceModal = function (sel) {
        var modal = typeof sel === "string" ? qs(sel) : sel;
        if (!modal) return;
        activeModal = modal;
        modal.classList.add("open");
        document.body.classList.add("modal-open");

        /* Focus first input inside */
        var firstInput = qs("input, select, button", modal);
        if (firstInput) setTimeout(function () { firstInput.focus(); }, 60);
    };

    /**
     * Close the attendance modal.
     * @param {string|Element} [sel] - optional; closes activeModal if omitted
     */
    kopila.closeAttendanceModal = function (sel) {
        var modal = sel
            ? (typeof sel === "string" ? qs(sel) : sel)
            : activeModal;
        if (!modal) return;
        modal.classList.remove("open");
        document.body.classList.remove("modal-open");
        if (modal === activeModal) activeModal = null;
    };

    function initAttendanceModal() {
        /* Escape key closes modal */
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && activeModal) {
                kopila.closeAttendanceModal();
            }
        });

        /* Backdrop click closes modal */
        document.addEventListener("click", function (e) {
            if (!activeModal) return;
            if (e.target.classList.contains("att-modal-backdrop") ||
                e.target.classList.contains("modal-scrim")) {
                kopila.closeAttendanceModal();
            }
        });

        /* Close buttons inside modals */
        document.addEventListener("click", function (e) {
            var closeBtn = e.target.closest("[data-modal-close]");
            if (closeBtn) {
                e.preventDefault();
                var target = closeBtn.getAttribute("data-modal-close");
                kopila.closeAttendanceModal(target || null);
            }
        });

        /* Open triggers */
        document.addEventListener("click", function (e) {
            var openBtn = e.target.closest("[data-modal-open]");
            if (openBtn) {
                e.preventDefault();
                var target = openBtn.getAttribute("data-modal-open");
                kopila.openAttendanceModal(target);
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  5. View Switcher                                                  */
    /* ------------------------------------------------------------------ */
    function initViewSwitcher() {
        document.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-view-switch]");
            if (!btn) return;
            e.preventDefault();

            var viewName = btn.getAttribute("data-view-switch");
            var container = btn.closest("[data-view-group]") || document;
            var groupName = (btn.closest("[data-view-group]") || {}).getAttribute
                ? btn.closest("[data-view-group]").getAttribute("data-view-group")
                : null;

            /* Update active button state in segmented control */
            var seg = btn.closest(".seg, .view-switcher");
            if (seg) {
                qsa("button, a", seg).forEach(function (b) {
                    b.classList.remove("active");
                });
                btn.classList.add("active");
            }

            /* Show/hide sections */
            var sections = groupName
                ? qsa('[data-view="' + groupName + '"]', container)
                : qsa("[data-view]");

            /* Actually, find all view targets that match */
            var allViews = qsa("[data-view-target]", container.parentElement || document);
            allViews.forEach(function (view) {
                if (view.getAttribute("data-view-target") === viewName) {
                    view.style.display = "";
                    view.classList.add("view-active");
                    view.classList.remove("view-hidden");
                } else {
                    view.style.display = "none";
                    view.classList.remove("view-active");
                    view.classList.add("view-hidden");
                }
            });
        });
    }

    /* ------------------------------------------------------------------ */
    /*  6. Matrix Date Filter                                             */
    /* ------------------------------------------------------------------ */
    function initMatrixDateFilter() {
        var form = qs(".att-matrix-filter, [data-matrix-filter]");
        if (!form) return;

        var dateFrom = qs('input[name="date_from"], #att-date-from', form);
        var dateTo   = qs('input[name="date_to"], #att-date-to', form);

        if (!dateFrom || !dateTo) return;

        function maybeSubmit() {
            if (dateFrom.value && dateTo.value) {
                /* Validate date range */
                if (dateFrom.value > dateTo.value) {
                    kopila.toast("Start date must be before end date");
                    return;
                }

                /* If this is inside an actual <form>, submit it */
                var parentForm = form.closest("form") || form;
                if (parentForm.tagName === "FORM") {
                    parentForm.submit();
                } else if (parentForm.hasAttribute("hx-get") || parentForm.hasAttribute("hx-post")) {
                    /* Trigger HTMX */
                    if (window.htmx) {
                        window.htmx.trigger(parentForm, "submit");
                    }
                } else {
                    /* Build URL and navigate */
                    var base = window.location.pathname;
                    var params = new URLSearchParams(window.location.search);
                    params.set("date_from", dateFrom.value);
                    params.set("date_to", dateTo.value);
                    window.location.href = base + "?" + params.toString();
                }
            }
        }

        dateFrom.addEventListener("change", maybeSubmit);
        dateTo.addEventListener("change", maybeSubmit);
    }

    /* ------------------------------------------------------------------ */
    /*  Submit / Reset Attendance Sheet                                   */
    /* ------------------------------------------------------------------ */
    function initSheetActions() {
        /* Submit sheet button */
        document.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-action='submit-sheet']");
            if (!btn) return;
            e.preventDefault();

            /* Mark unmarked students as absent */
            var unmarked = qsa("[data-student-id]:not([data-att-status])");
            if (unmarked.length > 0) {
                kopila.toast(unmarked.length + " students unmarked \u2014 marking as absent");
                unmarked.forEach(function (row) {
                    applyStatus(row, "a");
                });
            }

            updateCounters();

            /* If there is a form URL, submit */
            var url = btn.getAttribute("data-url") || btn.getAttribute("hx-post");
            if (url && !btn.hasAttribute("hx-post")) {
                var csrf = qs('input[name="csrf_token"]');
                var body = new FormData();
                body.append("action", "submit");
                if (csrf) body.append("csrf_token", csrf.value);
                fetch(url, {
                    method: "POST",
                    body: body,
                    headers: { "X-Requested-With": "XMLHttpRequest" }
                }).then(function (resp) {
                    if (resp.ok) {
                        kopila.toast("Attendance submitted \u00B7 locked for edits");
                    } else {
                        kopila.toast("Failed to submit \u2014 try again");
                    }
                });
            } else {
                kopila.toast("Attendance submitted \u00B7 locked for edits");
            }

            /* Disable all status buttons */
            qsa(".att-btn").forEach(function (b) { b.disabled = true; });
            btn.style.display = "none";
            var resetBtn = qs("[data-action='reset-sheet']");
            if (resetBtn) resetBtn.style.display = "";
        });

        /* Reset to draft button */
        document.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-action='reset-sheet']");
            if (!btn) return;
            e.preventDefault();

            qsa("[data-student-id]").forEach(function (row) {
                applyStatus(row, null);
            });
            updateCounters();

            /* Re-enable buttons */
            qsa(".att-btn").forEach(function (b) { b.disabled = false; });
            btn.style.display = "none";
            var submitBtn = qs("[data-action='submit-sheet']");
            if (submitBtn) submitBtn.style.display = "";

            kopila.toast("Sheet reset to draft");
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Boot                                                              */
    /* ------------------------------------------------------------------ */
    function init() {
        initAttendanceButtons();
        initPhotoGrid();
        initMarksInput();
        initAttendanceModal();
        initViewSwitcher();
        initMatrixDateFilter();
        initSheetActions();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
