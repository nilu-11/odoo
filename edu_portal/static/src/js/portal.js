/**
 * Kopila EMIS Portal — vanilla JS shell
 * Handles: icons, sidebar, command palette, theme, toasts,
 *          user menu, mobile drawer, notifications, HTMX hooks.
 *
 * No React, no build step. Works with server-rendered HTML.
 */
(function () {
    "use strict";

    /* ------------------------------------------------------------------ */
    /*  Namespace                                                         */
    /* ------------------------------------------------------------------ */
    var kopila = window.kopila = window.kopila || {};

    /* ------------------------------------------------------------------ */
    /*  Helpers                                                           */
    /* ------------------------------------------------------------------ */
    function qs(sel, root) { return (root || document).querySelector(sel); }
    function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

    function setCookie(name, value, days) {
        var d = new Date();
        d.setTime(d.getTime() + (days || 365) * 86400000);
        document.cookie = name + "=" + encodeURIComponent(value) +
            ";expires=" + d.toUTCString() + ";path=/;SameSite=Lax";
    }

    function getCookie(name) {
        var m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
        return m ? decodeURIComponent(m[2]) : null;
    }

    /* ------------------------------------------------------------------ */
    /*  1. SVG Icon System                                                */
    /* ------------------------------------------------------------------ */
    var ICON_PATHS = {
        home:       '<path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-8.5Z"/>',
        book:       '<path d="M4 5a2 2 0 0 1 2-2h12v15H6a2 2 0 0 0-2 2V5Z"/><path d="M6 18h12v3H6a2 2 0 0 1 0-3Z"/>',
        check:      '<path d="M4 12.5 9 17l11-11"/>',
        x:          '<path d="M6 6l12 12M6 18 18 6"/>',
        clock:      '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        users:      '<circle cx="9" cy="9" r="3.2"/><path d="M3 20c0-3 2.8-5 6-5s6 2 6 5"/><path d="M15 10.5a3 3 0 0 0 0-5.8"/><path d="M17 20c0-2.5 1.5-4 4-4"/>',
        user:       '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6"/>',
        pen:        '<path d="M14 5l5 5L8 21H3v-5L14 5Z"/><path d="M12 7l5 5"/>',
        grid:       '<rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><rect x="14" y="14" width="7" height="7" rx="1.2"/>',
        msg:        '<path d="M4 5h16v11H8l-4 4V5Z"/>',
        bell:       '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16Z"/><path d="M10 19a2 2 0 0 0 4 0"/>',
        mega:       '<path d="M4 9v6l11 4V5L4 9Z"/><path d="M15 8v8"/><path d="M18 10a3 3 0 0 1 0 4"/>',
        cal:        '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
        chart:      '<path d="M4 20V9M10 20V4M16 20v-8M22 20H2"/>',
        coin:       '<circle cx="12" cy="12" r="9"/><path d="M8 10c0-1.4 1.8-2.5 4-2.5s4 1.1 4 2.5-1.5 2-4 2.5-4 1.1-4 2.5 1.8 2.5 4 2.5 4-1.1 4-2.5"/><path d="M12 5v14"/>',
        flag:       '<path d="M5 22V3h12l-2 4 2 4H5"/>',
        search:     '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/>',
        menu:       '<path d="M4 7h16M4 12h16M4 17h16"/>',
        plus:       '<path d="M12 5v14M5 12h14"/>',
        caret:      '<path d="M6 9l6 6 6-6"/>',
        caretRight: '<path d="M9 6l6 6-6 6"/>',
        dots:       '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
        filter:     '<path d="M4 5h16l-6 8v6l-4-2v-4L4 5Z"/>',
        download:   '<path d="M12 4v12"/><path d="M7 11l5 5 5-5"/><path d="M4 20h16"/>',
        settings:   '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
        star:       '<path d="M12 3l2.8 5.8 6.2.9-4.5 4.4 1.1 6.3L12 17.4 6.4 20.4l1.1-6.3L3 9.7l6.2-.9L12 3Z"/>',
        paper:      '<path d="M6 3h9l5 5v13H6V3Z"/><path d="M15 3v5h5"/><path d="M9 13h7M9 17h7M9 9h3"/>',
        sparkle:    '<path d="M12 3v6M12 15v6M3 12h6M15 12h6"/><path d="M6 6l3 3M18 18l-3-3M6 18l3-3M18 6l-3 3"/>',
        inbox:      '<path d="M3 13l2-9h14l2 9v7H3v-7Z"/><path d="M3 13h6l1 3h4l1-3h6"/>',
        moon:       '<path d="M20 15A8 8 0 0 1 9 4a8 8 0 1 0 11 11Z"/>',
        sun:        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
        sliders:    '<path d="M4 7h10M18 7h2M4 12h2M10 12h10M4 17h14M20 17h0"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="17" r="2"/>',
        panel:      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>'
    };

    /**
     * Return an SVG HTML string for the named icon.
     * @param {string} name  - icon key
     * @param {number} [size=16] - width and height
     * @returns {string} SVG markup
     */
    kopila.icon = function (name, size) {
        var s = size || 16;
        var inner = ICON_PATHS[name] || "";
        return '<svg class="ico" width="' + s + '" height="' + s +
            '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
            inner + "</svg>";
    };

    /* ------------------------------------------------------------------ */
    /*  2. Sidebar Toggle                                                 */
    /* ------------------------------------------------------------------ */
    var SIDEBAR_CYCLE_DESKTOP = ["labeled", "rail", "hidden"];
    var html = document.documentElement;

    function isMobile() { return window.innerWidth <= 900; }

    function getSidebar() {
        return html.getAttribute("data-sidebar") || "labeled";
    }

    function setSidebar(mode) {
        html.setAttribute("data-sidebar", mode);
        setCookie("kopila_sidebar", mode);
    }

    function cycleSidebar() {
        if (isMobile()) {
            toggleMobileDrawer();
            return;
        }
        var cur = getSidebar();
        var idx = SIDEBAR_CYCLE_DESKTOP.indexOf(cur);
        var next = SIDEBAR_CYCLE_DESKTOP[(idx + 1) % SIDEBAR_CYCLE_DESKTOP.length];
        setSidebar(next);
    }

    kopila.cycleSidebar = cycleSidebar;

    /* ------------------------------------------------------------------ */
    /*  3. Command Palette                                                */
    /* ------------------------------------------------------------------ */
    var cmdOpen = false;
    var cmdFocus = 0;
    var cmdItems = [];
    var cmdEl = null;
    var cmdInput = null;
    var cmdList = null;

    /* Base navigation items — mirrors shell.jsx NAV lists */
    var CMD_BASE = [
        { group: "Navigate", id: "today",         label: "Today",            meta: "G T",  url: "/my/portal" },
        { group: "Navigate", id: "attendance",     label: "Take attendance",  meta: "G A",  url: "/my/attendance" },
        { group: "Navigate", id: "marking",        label: "Mark exam papers", meta: "G M",  url: "/my/marking" },
        { group: "Navigate", id: "gradebook",      label: "Gradebook",        meta: "G G",  url: "/my/gradebook" },
        { group: "Navigate", id: "messages",       label: "Messages",         meta: "",     url: "/my/messages" },
        { group: "Navigate", id: "announcements",  label: "Announcements",    meta: "",     url: "/my/announcements" },
        { group: "Navigate", id: "calendar",       label: "Calendar",         meta: "",     url: "/my/calendar" },
        { group: "Navigate", id: "reports",        label: "Report cards",     meta: "",     url: "/my/reports" },
        { group: "Navigate", id: "behavior",       label: "Behavior notes",   meta: "",     url: "/my/behavior" },
        { group: "Navigate", id: "fees",           label: "Fees overview",    meta: "",     url: "/my/fees" },
        { group: "Actions",  id: "new-ann",        label: "New announcement", meta: "N A",  url: "/my/announcements#new" },
        { group: "Actions",  id: "new-msg",        label: "New message",      meta: "N M",  url: "/my/messages#new" }
    ];

    function getCourses() {
        /* Try data-courses attribute on <body> first, then collect from DOM */
        var raw = document.body.getAttribute("data-courses");
        if (raw) {
            try { return JSON.parse(raw); } catch (_) { /* fallback */ }
        }
        /* Collect from sidebar nav-course links */
        var out = [];
        qsa(".sidebar .nav-course").forEach(function (el) {
            out.push({
                label: (el.textContent || "").trim(),
                url: el.getAttribute("href") || "#"
            });
        });
        return out;
    }

    function buildCmdItems(query) {
        var items = CMD_BASE.slice();
        var courses = getCourses();
        courses.forEach(function (c) {
            items.push({
                group: "Courses",
                id: "course:" + (c.id || c.label),
                label: c.code ? (c.code + " \u00B7 " + c.title) : c.label,
                meta: c.semester || "",
                url: c.url || ("/my/classroom/" + (c.id || ""))
            });
        });
        if (!query) return items;
        var q = query.toLowerCase();
        return items.filter(function (it) {
            return it.label.toLowerCase().indexOf(q) !== -1;
        });
    }

    function renderCmdList() {
        if (!cmdList) return;
        cmdItems = buildCmdItems(cmdInput ? cmdInput.value : "");
        var html = "";
        var lastGroup = "";
        if (cmdItems.length === 0) {
            html = '<div style="padding:20px;color:var(--ink-softer);font-size:13px">No results</div>';
        } else {
            cmdItems.forEach(function (it, i) {
                if (it.group !== lastGroup) {
                    html += '<div class="cmd-group">' + it.group + '</div>';
                    lastGroup = it.group;
                }
                var iconName = it.group === "Courses" ? "book" :
                               it.group === "Actions" ? "sparkle" : "caretRight";
                html += '<div class="cmd-row' + (cmdFocus === i ? " focus" : "") +
                    '" data-idx="' + i + '">' +
                    kopila.icon(iconName, 14) +
                    '<span>' + it.label + '</span>' +
                    '<span class="meta">' + (it.meta || "") + '</span>' +
                    '</div>';
            });
        }
        cmdList.innerHTML = html;

        /* Ensure focused row is visible */
        var focused = cmdList.querySelector(".cmd-row.focus");
        if (focused) {
            focused.scrollIntoView({ block: "nearest" });
        }
    }

    function cmdNavigate(item) {
        if (item && item.url) {
            window.location.href = item.url;
        }
    }

    function openCmd() {
        if (cmdOpen) return;
        cmdOpen = true;
        cmdFocus = 0;

        /* Build DOM if first time */
        if (!cmdEl) {
            cmdEl = document.createElement("div");
            cmdEl.className = "scrim";
            cmdEl.innerHTML =
                '<div class="cmd">' +
                    '<input class="cmd-input" placeholder="Search for a page, student, or action\u2026" />' +
                    '<div class="cmd-list"></div>' +
                '</div>';
            document.body.appendChild(cmdEl);

            cmdInput = cmdEl.querySelector(".cmd-input");
            cmdList = cmdEl.querySelector(".cmd-list");

            /* Prevent close when clicking inside palette */
            cmdEl.querySelector(".cmd").addEventListener("click", function (e) {
                e.stopPropagation();
            });

            /* Backdrop click → close */
            cmdEl.addEventListener("click", function () { closeCmd(); });

            /* Input typing → filter */
            cmdInput.addEventListener("input", function () {
                cmdFocus = 0;
                renderCmdList();
            });

            /* Keyboard inside input */
            cmdInput.addEventListener("keydown", function (e) {
                if (e.key === "ArrowDown") {
                    e.preventDefault();
                    cmdFocus = Math.min(cmdFocus + 1, cmdItems.length - 1);
                    renderCmdList();
                } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    cmdFocus = Math.max(cmdFocus - 1, 0);
                    renderCmdList();
                } else if (e.key === "Enter") {
                    e.preventDefault();
                    var it = cmdItems[cmdFocus];
                    if (it) { cmdNavigate(it); closeCmd(); }
                } else if (e.key === "Escape") {
                    closeCmd();
                }
            });

            /* Row hover + click */
            cmdList.addEventListener("mouseover", function (e) {
                var row = e.target.closest(".cmd-row");
                if (row) {
                    cmdFocus = parseInt(row.getAttribute("data-idx"), 10);
                    renderCmdList();
                }
            });
            cmdList.addEventListener("click", function (e) {
                var row = e.target.closest(".cmd-row");
                if (row) {
                    var idx = parseInt(row.getAttribute("data-idx"), 10);
                    var it = cmdItems[idx];
                    if (it) { cmdNavigate(it); closeCmd(); }
                }
            });
        }

        cmdEl.classList.add("open");
        cmdInput.value = "";
        renderCmdList();
        setTimeout(function () { cmdInput.focus(); }, 30);
    }

    function closeCmd() {
        if (!cmdOpen) return;
        cmdOpen = false;
        if (cmdEl) cmdEl.classList.remove("open");
    }

    kopila.openCmd = openCmd;
    kopila.closeCmd = closeCmd;

    /* ------------------------------------------------------------------ */
    /*  4. Theme System                                                   */
    /* ------------------------------------------------------------------ */
    function restorePreferences() {
        var theme   = getCookie("kopila_theme")   || "saffron";
        var mode    = getCookie("kopila_mode")    || "light";
        var density = getCookie("kopila_density") || "comfortable";
        var sidebar = getCookie("kopila_sidebar") || "labeled";

        html.setAttribute("data-theme", theme);
        html.setAttribute("data-mode", mode);
        html.setAttribute("data-density", density);
        html.setAttribute("data-sidebar", sidebar);
    }

    function getMode() {
        return html.getAttribute("data-mode") || "light";
    }

    function toggleMode() {
        var next = getMode() === "dark" ? "light" : "dark";
        html.setAttribute("data-mode", next);
        setCookie("kopila_mode", next);

        /* Update theme toggle icon if present */
        var btn = qs(".portal-topbar .theme-toggle, .topbar .theme-toggle");
        if (btn) {
            btn.innerHTML = kopila.icon(next === "dark" ? "sun" : "moon", 16);
        }
    }

    kopila.toggleMode = toggleMode;
    kopila.getMode = getMode;

    function setTheme(name) {
        html.setAttribute("data-theme", name);
        setCookie("kopila_theme", name);
    }
    kopila.setTheme = setTheme;

    function setDensity(name) {
        html.setAttribute("data-density", name);
        setCookie("kopila_density", name);
    }
    kopila.setDensity = setDensity;

    /* ------------------------------------------------------------------ */
    /*  5. Toast Notifications                                            */
    /* ------------------------------------------------------------------ */
    var toastLayer = null;

    function ensureToastLayer() {
        if (toastLayer) return;
        toastLayer = document.createElement("div");
        toastLayer.className = "toast-layer";
        document.body.appendChild(toastLayer);
    }

    /**
     * Show a toast notification.
     * @param {string} message
     * @param {number} [duration=2200] - auto-dismiss ms
     */
    kopila.toast = function (message, duration) {
        ensureToastLayer();
        var el = document.createElement("div");
        el.className = "toast";
        el.textContent = message;
        toastLayer.appendChild(el);

        /* Trigger reflow for transition */
        void el.offsetWidth;
        el.classList.add("show");

        setTimeout(function () {
            el.classList.remove("show");
            el.classList.add("hide");
            el.addEventListener("transitionend", function () {
                if (el.parentNode) el.parentNode.removeChild(el);
            });
            /* Fallback removal */
            setTimeout(function () {
                if (el.parentNode) el.parentNode.removeChild(el);
            }, 400);
        }, duration || 2200);
    };

    /* ------------------------------------------------------------------ */
    /*  6. User Menu Dropdown                                             */
    /* ------------------------------------------------------------------ */
    function initUserMenu() {
        var trigger = qs(".user-menu-trigger, .sidebar-footer .avatar");
        var menu = qs(".user-menu-dropdown");
        if (!trigger || !menu) return;

        trigger.addEventListener("click", function (e) {
            e.stopPropagation();
            menu.classList.toggle("open");
        });

        document.addEventListener("click", function (e) {
            if (!menu.contains(e.target) && !trigger.contains(e.target)) {
                menu.classList.remove("open");
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  7. Mobile Drawer                                                  */
    /* ------------------------------------------------------------------ */
    var drawerOpen = false;
    var backdrop = null;

    function ensureBackdrop() {
        if (backdrop) return;
        backdrop = document.createElement("div");
        backdrop.className = "mobile-backdrop";
        document.body.appendChild(backdrop);
        backdrop.addEventListener("click", closeMobileDrawer);
    }

    function openMobileDrawer() {
        if (drawerOpen) return;
        ensureBackdrop();
        drawerOpen = true;
        html.classList.add("drawer-open");
        backdrop.classList.add("show");
    }

    function closeMobileDrawer() {
        if (!drawerOpen) return;
        drawerOpen = false;
        html.classList.remove("drawer-open");
        if (backdrop) backdrop.classList.remove("show");
    }

    function toggleMobileDrawer() {
        if (drawerOpen) closeMobileDrawer(); else openMobileDrawer();
    }

    kopila.openMobileDrawer = openMobileDrawer;
    kopila.closeMobileDrawer = closeMobileDrawer;

    /* Close drawer when clicking any sidebar link (mobile) */
    function initMobileDrawerLinks() {
        qsa(".sidebar a").forEach(function (a) {
            a.addEventListener("click", function () {
                if (isMobile()) closeMobileDrawer();
            });
        });
    }

    /* ------------------------------------------------------------------ */
    /*  8. Notification Dot — handled via CSS; no JS needed unless        */
    /*     we want dynamic updates.                                       */
    /* ------------------------------------------------------------------ */
    kopila.setNotificationDot = function (show) {
        var dot = qs(".topbar .dot, .portal-topbar .dot");
        if (dot) dot.style.display = show ? "" : "none";
    };

    /* ------------------------------------------------------------------ */
    /*  9. HTMX Integration                                               */
    /* ------------------------------------------------------------------ */
    function initHtmx() {
        document.body.addEventListener("htmx:afterSwap", function (evt) {
            var target = evt.detail.target || evt.target;
            if (target) {
                target.classList.add("flash-success");
                setTimeout(function () {
                    target.classList.remove("flash-success");
                }, 1200);
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  10. Breadcrumbs                                                   */
    /* ------------------------------------------------------------------ */
    function initBreadcrumbs() {
        var content = qs(".content");
        if (!content) return;
        var raw = content.getAttribute("data-crumbs");
        if (!raw) return;

        var parts;
        try { parts = JSON.parse(raw); } catch (_) {
            parts = raw.split("/").map(function (s) { return s.trim(); }).filter(Boolean);
        }

        var crumbsEl = qs(".topbar .crumbs, .portal-topbar .crumbs");
        if (!crumbsEl || parts.length === 0) return;

        var html = "";
        parts.forEach(function (c, i) {
            if (i > 0) html += '<span class="sep">/</span>';
            var cls = i === parts.length - 1 ? "current" : "crumb-hide-sm";
            html += '<span class="' + cls + '">' + c + '</span>';
        });
        crumbsEl.innerHTML = html;
    }

    /* ------------------------------------------------------------------ */
    /*  Global Keyboard Shortcuts                                         */
    /* ------------------------------------------------------------------ */
    function initKeyboard() {
        document.addEventListener("keydown", function (e) {
            /* Cmd/Ctrl+K — command palette */
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                if (cmdOpen) closeCmd(); else openCmd();
                return;
            }
            /* Escape — close anything open */
            if (e.key === "Escape") {
                if (cmdOpen) { closeCmd(); return; }
                if (drawerOpen) { closeMobileDrawer(); return; }
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Responsive handler — switch sidebar to drawer on resize           */
    /* ------------------------------------------------------------------ */
    function initResponsive() {
        var mql = window.matchMedia("(max-width: 900px)");
        function onChange(e) {
            if (e.matches) {
                /* Entering mobile */
                closeMobileDrawer();
            } else {
                /* Entering desktop — close drawer, restore sidebar */
                closeMobileDrawer();
            }
        }
        if (mql.addEventListener) {
            mql.addEventListener("change", onChange);
        } else if (mql.addListener) {
            mql.addListener(onChange);
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Wire up topbar buttons                                            */
    /* ------------------------------------------------------------------ */
    function initTopbar() {
        /* Sidebar toggle */
        qsa(".sidebar-toggle, .portal-topbar .sidebar-toggle, .topbar .iconbtn[title*='Sidebar']").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                cycleSidebar();
            });
        });

        /* Command palette trigger */
        qsa(".cmd-trigger").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                openCmd();
            });
        });

        /* Theme toggle */
        qsa(".theme-toggle, .topbar .iconbtn[title*='theme'], .topbar .iconbtn[title*='Theme']").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                toggleMode();
            });
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Boot                                                              */
    /* ------------------------------------------------------------------ */
    function init() {
        restorePreferences();
        initTopbar();
        initUserMenu();
        initMobileDrawerLinks();
        initBreadcrumbs();
        initKeyboard();
        initResponsive();
        initHtmx();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
