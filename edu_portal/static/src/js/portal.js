/* EMIS Portal — main JS (sidebar, role switcher, misc UI) */
(function() {
    'use strict';

    // ─── Sidebar toggle ────────────────────────────────────
    function initSidebarToggle() {
        const toggle = document.querySelector('[data-sidebar-toggle]');
        const body = document.body;
        if (!toggle) return;

        toggle.addEventListener('click', function() {
            body.classList.toggle('sidebar-collapsed');
            // Persist state via cookie (server reads on next request)
            const collapsed = body.classList.contains('sidebar-collapsed');
            document.cookie = `portal_sidebar_collapsed=${collapsed ? '1' : '0'}; path=/; max-age=31536000`;
        });
    }

    // ─── Mobile drawer backdrop ────────────────────────────
    function initMobileDrawer() {
        const backdrop = document.querySelector('[data-sidebar-backdrop]');
        const body = document.body;
        if (!backdrop) return;
        backdrop.addEventListener('click', function() {
            body.classList.remove('sidebar-open');
        });
    }

    // ─── User menu dropdown ────────────────────────────────
    function initUserMenu() {
        const trigger = document.querySelector('[data-user-menu-trigger]');
        const menu = document.querySelector('[data-user-menu]');
        if (!trigger || !menu) return;
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            menu.classList.toggle('open');
        });
        document.addEventListener('click', function() {
            menu.classList.remove('open');
        });
    }

    // ─── HTMX success flash ────────────────────────────────
    function initHtmxFlash() {
        document.body.addEventListener('htmx:afterSwap', function(evt) {
            const target = evt.detail.target;
            if (target && target.classList) {
                target.classList.add('flash-success');
                setTimeout(() => target.classList.remove('flash-success'), 600);
            }
        });
    }

    // ─── Init on DOM ready ─────────────────────────────────
    document.addEventListener('DOMContentLoaded', function() {
        initSidebarToggle();
        initMobileDrawer();
        initUserMenu();
        initHtmxFlash();
    });
})();
