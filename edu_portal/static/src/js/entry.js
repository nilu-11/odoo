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

    document.addEventListener('DOMContentLoaded', function() {
        initAttendanceModalTriggers();
        initAutoOpenModal();
        initAttendanceKeyboard();
        initMarksTabNavigation();
        initMatrixDateFilter();
    });

    // After every HTMX swap, update counters + re-init keyboard
    document.body.addEventListener('htmx:afterSwap', function() {
        updateAttendanceCounters();
        initMarksTabNavigation();
    });
})();
