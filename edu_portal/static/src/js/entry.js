/* EMIS Portal — data entry grid helpers (attendance, marks) */
(function() {
    'use strict';

    // ─── Attendance: keyboard shortcuts ─────────────────────
    // Press P, A, L, E while focused on a row to mark that student
    function initAttendanceKeyboard() {
        document.addEventListener('keydown', function(e) {
            const row = e.target.closest('[data-attendance-row]');
            if (!row) return;
            const keyMap = {
                'p': 'present', 'P': 'present',
                'a': 'absent',  'A': 'absent',
                'l': 'late',    'L': 'late',
                'e': 'excused', 'E': 'excused',
            };
            const status = keyMap[e.key];
            if (!status) return;
            e.preventDefault();
            const lineId = row.getAttribute('data-line-id');
            htmx.ajax('POST', '/portal/teacher/attendance/mark', {
                target: row,
                swap: 'outerHTML',
                values: { line_id: lineId, status: status },
            });
            // Move focus to next row
            const nextRow = row.nextElementSibling;
            if (nextRow && nextRow.hasAttribute('data-attendance-row')) {
                nextRow.focus();
            }
        });
    }

    // ─── Marks entry: tab navigation ────────────────────────
    function initMarksTabNavigation() {
        const inputs = document.querySelectorAll('[data-marks-input]');
        inputs.forEach((input, idx) => {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const next = inputs[idx + 1];
                    if (next) next.focus();
                }
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        initAttendanceKeyboard();
        initMarksTabNavigation();
    });
    // Re-init after HTMX swaps (grids may be reloaded)
    document.body.addEventListener('htmx:afterSwap', function() {
        initMarksTabNavigation();
    });
})();
