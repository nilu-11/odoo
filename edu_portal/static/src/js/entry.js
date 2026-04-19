/* EMIS Portal — data entry helpers (attendance modal, marks) */
(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    //  Attendance Modal
    // ═══════════════════════════════════════════════════════════

    function openAttendanceModal() {
        var modal = document.getElementById('attendance-modal');
        if (!modal) return;
        modal.classList.add('att-modal--open');
        document.body.style.overflow = 'hidden';
        updateAttendanceCounters();
        // Focus first student row for keyboard nav
        var first = modal.querySelector('[data-attendance-row]');
        if (first) first.focus();
    }

    function closeAttendanceModal() {
        var modal = document.getElementById('attendance-modal');
        if (!modal) return;
        modal.classList.remove('att-modal--open');
        document.body.style.overflow = '';
    }

    // Open buttons
    function initAttendanceModalTriggers() {
        document.querySelectorAll('[data-att-open]').forEach(function(btn) {
            btn.addEventListener('click', openAttendanceModal);
        });
        document.querySelectorAll('[data-att-close]').forEach(function(el) {
            el.addEventListener('click', closeAttendanceModal);
        });
        // Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeAttendanceModal();
        });
    }

    // Auto-open if server says so
    function initAutoOpenModal() {
        var modal = document.getElementById('attendance-modal');
        if (modal && modal.classList.contains('att-modal--open')) {
            document.body.style.overflow = 'hidden';
            updateAttendanceCounters();
        }
    }

    // ═══════════════════════════════════════════════════════════
    //  Live Counters
    // ═══════════════════════════════════════════════════════════

    function updateAttendanceCounters() {
        var rows = document.querySelectorAll('#att-student-list .att-student-row');
        var counts = { present: 0, absent: 0, late: 0, excused: 0 };
        rows.forEach(function(row) {
            var active = row.querySelector('.att-status-btn.active');
            if (!active) return;
            if (active.classList.contains('att-status-btn--present')) counts.present++;
            else if (active.classList.contains('att-status-btn--absent')) counts.absent++;
            else if (active.classList.contains('att-status-btn--late')) counts.late++;
            else if (active.classList.contains('att-status-btn--excused')) counts.excused++;
        });
        var keys = ['present', 'absent', 'late', 'excused'];
        keys.forEach(function(k) {
            var el = document.getElementById('att-count-' + k);
            if (el) el.textContent = counts[k];
        });
    }

    // ═══════════════════════════════════════════════════════════
    //  Keyboard Shortcuts (P, A, L, E) for attendance rows
    // ═══════════════════════════════════════════════════════════

    function initAttendanceKeyboard() {
        document.addEventListener('keydown', function(e) {
            var row = e.target.closest('[data-attendance-row]');
            if (!row) return;
            // Don't intercept if inside an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            var keyMap = {
                'p': 'present', 'P': 'present',
                'a': 'absent',  'A': 'absent',
                'l': 'late',    'L': 'late',
                'e': 'excused', 'E': 'excused',
            };
            var status = keyMap[e.key];
            if (!status) return;
            e.preventDefault();
            var lineId = row.getAttribute('data-line-id');
            if (!lineId) return;
            htmx.ajax('POST', '/portal/teacher/classroom/attendance/mark', {
                target: row,
                swap: 'outerHTML',
                values: { line_id: lineId, status: status },
            });
            // Move focus to next row
            var nextRow = row.nextElementSibling;
            if (nextRow && nextRow.hasAttribute('data-attendance-row')) {
                nextRow.focus();
            }
        });
    }

    // ═══════════════════════════════════════════════════════════
    //  Marks entry: tab navigation
    // ═══════════════════════════════════════════════════════════

    function initMarksTabNavigation() {
        var inputs = document.querySelectorAll('[data-marks-input]');
        inputs.forEach(function(input, idx) {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    var next = inputs[idx + 1];
                    if (next) next.focus();
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════
    //  Attendance Matrix: date range filter
    // ═══════════════════════════════════════════════════════════

    function initMatrixDateFilter() {
        var form = document.getElementById('att-matrix-filter');
        if (!form) return;
        // Auto-submit when both dates are filled
        var inputs = form.querySelectorAll('input[type="date"]');
        inputs.forEach(function(input) {
            input.addEventListener('change', function() {
                var from = form.querySelector('[name="date_from"]');
                var to = form.querySelector('[name="date_to"]');
                if (from && from.value && to && to.value) {
                    form.submit();
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════
    //  Init
    // ═══════════════════════════════════════════════════════════

    // ─── Attendance view switch (List / Grid) ──────────────
    function initAttendanceViewSwitch() {
        var sw = document.getElementById('att-view-switch');
        if (!sw) return;
        sw.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-att-view]');
            if (!btn) return;
            var view = btn.getAttribute('data-att-view');
            sw.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            var list = document.getElementById('att-student-list');
            var grid = document.getElementById('att-photo-grid');
            if (view === 'grid') {
                if (list) list.style.display = 'none';
                if (grid) grid.classList.add('active');
            } else {
                if (list) list.style.display = '';
                if (grid) grid.classList.remove('active');
            }
        });
    }

    // ─── Photo grid: cycle status on click ───────────────────
    var STATUS_CYCLE = ['present', 'absent', 'late', 'excused'];
    window.cyclePhotoStatus = function(card) {
        var lineId = card.getAttribute('data-line-id');
        var currentClass = STATUS_CYCLE.find(function(s) { return card.classList.contains('status-' + s); });
        var nextIdx = currentClass ? (STATUS_CYCLE.indexOf(currentClass) + 1) % STATUS_CYCLE.length : 0;
        var nextStatus = STATUS_CYCLE[nextIdx];

        // Remove old status classes
        STATUS_CYCLE.forEach(function(s) { card.classList.remove('status-' + s); });
        card.classList.add('status-' + nextStatus);
        var statusEl = card.querySelector('.att-photo-status');
        if (statusEl) statusEl.textContent = nextStatus.charAt(0).toUpperCase() + nextStatus.slice(1);

        // Fire HTMX POST to persist
        var csrf = document.querySelector('[name="csrf_token"]');
        var body = new FormData();
        body.append('line_id', lineId);
        body.append('status', nextStatus);
        if (csrf) body.append('csrf_token', csrf.value);
        fetch('/portal/teacher/classroom/attendance/mark', { method: 'POST', body: body })
            .then(function() { updateAttendanceCounters(); syncGridFromList(); });
    };

    // Sync list row active buttons from grid (after grid click)
    function syncGridFromList() {
        var grid = document.getElementById('att-photo-grid');
        var list = document.getElementById('att-student-list');
        if (!grid || !list) return;
        grid.querySelectorAll('.att-photo-card').forEach(function(card) {
            var lineId = card.getAttribute('data-line-id');
            var status = STATUS_CYCLE.find(function(s) { return card.classList.contains('status-' + s); });
            if (!status) return;
            // Find matching row in list and update its active button
            var row = list.querySelector('[data-line-id="' + lineId + '"]');
            if (!row) return;
            row.querySelectorAll('.att-status-btn').forEach(function(btn) { btn.classList.remove('active'); });
            var targetBtn = row.querySelector('.att-status-btn--' + status);
            if (targetBtn) targetBtn.classList.add('active');
        });
    }

    // ═══════════════════════════════════════════════════════════

    document.addEventListener('DOMContentLoaded', function() {
        initAttendanceModalTriggers();
        initAutoOpenModal();
        initAttendanceKeyboard();
        initMarksTabNavigation();
        initMatrixDateFilter();
        initAttendanceViewSwitch();
    });

    // After every HTMX swap, update counters + re-init keyboard
    document.body.addEventListener('htmx:afterSwap', function() {
        updateAttendanceCounters();
        initMarksTabNavigation();
    });
})();
