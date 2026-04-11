/* EMIS Portal — main JS (sidebar, role switcher, misc UI) */
(function() {
    'use strict';

    const MOBILE_BREAKPOINT = 768;
    const isMobile = () => window.innerWidth <= MOBILE_BREAKPOINT;

    // ─── Sidebar toggle ────────────────────────────────────
    //
    // On desktop (> 768px): toggles `sidebar-collapsed` (icon rail mode).
    // On mobile  (≤ 768px): toggles `sidebar-open`       (slide-in drawer).
    //
    // The server reads `portal_sidebar_collapsed` from a cookie to restore
    // desktop state on next page load. Mobile drawer state is ephemeral —
    // always closed on navigation.
    function initSidebarToggle() {
        const toggle = document.querySelector('[data-sidebar-toggle]');
        const body = document.body;
        if (!toggle) return;

        toggle.addEventListener('click', function(e) {
            e.stopPropagation();
            if (isMobile()) {
                body.classList.toggle('sidebar-open');
            } else {
                body.classList.toggle('sidebar-collapsed');
                const collapsed = body.classList.contains('sidebar-collapsed');
                document.cookie = `portal_sidebar_collapsed=${collapsed ? '1' : '0'}; path=/; max-age=31536000`;
            }
        });

        // Close the mobile drawer if the viewport is resized up to desktop.
        window.addEventListener('resize', function() {
            if (!isMobile()) body.classList.remove('sidebar-open');
        });
    }

    // ─── Mobile drawer backdrop + outside-click dismiss ────
    //
    // On mobile, clicking anywhere outside the sidebar (including the
    // pseudo-backdrop) closes the drawer. Clicking a sidebar link also
    // closes it so the link's navigation visibly takes over.
    function initMobileDrawer() {
        const body = document.body;
        const sidebar = document.querySelector('[data-sidebar]');
        if (!sidebar) return;

        document.addEventListener('click', function(e) {
            if (!isMobile()) return;
            if (!body.classList.contains('sidebar-open')) return;
            if (sidebar.contains(e.target)) return;
            if (e.target.closest('[data-sidebar-toggle]')) return;
            body.classList.remove('sidebar-open');
        });

        sidebar.addEventListener('click', function(e) {
            if (!isMobile()) return;
            const link = e.target.closest('a');
            if (link) body.classList.remove('sidebar-open');
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
