// SEC UMS — UI behaviours (theme, sidebar, toasts, confirms, loader)
(function () {
    "use strict";

    /* ---------------------------------------------------------------
       Theme toggle (light / dark), persisted in localStorage
       --------------------------------------------------------------- */
    function currentTheme() {
        return document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
    }
    function paintThemeIcon() {
        var dark = currentTheme() === "dark";
        var iD = document.getElementById("themeIconDark");
        var iL = document.getElementById("themeIconLight");
        if (!iD || !iL) return;
        iD.classList.toggle("d-none", dark);
        iL.classList.toggle("d-none", !dark);
    }
    function toggleTheme() {
        var next = currentTheme() === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", next);
        localStorage.setItem("sec-theme", next);
        paintThemeIcon();
    }

    document.addEventListener("DOMContentLoaded", function () {
        paintThemeIcon();
        var t = document.getElementById("themeToggle");
        if (t) t.addEventListener("click", toggleTheme);

        /* -----------------------------------------------------------
           Mobile sidebar (off-canvas behaviour)
           ----------------------------------------------------------- */
        var toggle = document.getElementById("sidebarToggle");
        var backdrop = document.getElementById("sidebarBackdrop");
        if (toggle) toggle.addEventListener("click", function () {
            document.body.classList.toggle("sidebar-open");
        });
        if (backdrop) backdrop.addEventListener("click", function () {
            document.body.classList.remove("sidebar-open");
        });

        /* -----------------------------------------------------------
           Top progress loader — shows while the browser navigates
           ----------------------------------------------------------- */
        var loader = document.getElementById("sec-loader");
        if (loader) {
            window.addEventListener("beforeunload", function () {
                loader.classList.add("loading");
            });
            // show loader on real link/form navigation inside the app
            document.addEventListener("submit", function (e) {
                if (!e.target.dataset.noLoader) loader.classList.add("loading");
            });
        }

        /* -----------------------------------------------------------
           SweetAlert2 integration
           ----------------------------------------------------------- */
        var hasSwal = typeof window.Swal !== "undefined";
        var Toast = hasSwal ? Swal.mixin({
            toast: true,
            position: "top-end",
            showConfirmButton: false,
            timer: 3400,
            timerProgressBar: true,
            didOpen: function (toast) {
                toast.addEventListener("mouseenter", Swal.stopTimer);
                toast.addEventListener("mouseleave", Swal.resumeTimer);
            }
        }) : null;

        var iconByTag = {
            success: "success",
            error: "error",
            warning: "warning",
            info: "info",
            debug: "info"
        };

        // flash messages -> toast notifications
        document.querySelectorAll(".flash-message").forEach(function (el) {
            var text = el.textContent.trim();
            el.remove();
            if (!text) return;
            if (Toast) {
                Toast.fire({ icon: iconByTag[el.dataset.tag] || "info", title: text });
            } else {
                window.alert(text);
            }
        });

        // data-confirm="message" forms/buttons -> branded confirm dialog
        document.querySelectorAll("[data-confirm]").forEach(function (el) {
            var ask = function (proceed) {
                if (!hasSwal) {
                    if (window.confirm(el.dataset.confirm)) proceed();
                    return;
                }
                Swal.fire({
                    title: "Please confirm",
                    text: el.dataset.confirm,
                    icon: "warning",
                    showCancelButton: true,
                    confirmButtonText: "Yes, continue",
                    cancelButtonText: "Cancel",
                    confirmButtonColor: "#8e1a35",
                    cancelButtonColor: "#68708c",
                    reverseButtons: true,
                    focusCancel: true
                }).then(function (r) { if (r.isConfirmed) proceed(); });
            };
            if (el.tagName === "FORM") {
                el.addEventListener("submit", function (e) {
                    if (el.dataset.confirmed === "1") return;
                    e.preventDefault();
                    ask(function () {
                        el.dataset.confirmed = "1";
                        el.requestSubmit ? el.requestSubmit() : el.submit();
                    });
                });
            } else {
                el.addEventListener("click", function (e) {
                    e.preventDefault();
                    ask(function () { window.location.href = el.href; });
                });
            }
        });

        /* -----------------------------------------------------------
           Login page demo chips: click to fill the form
           ----------------------------------------------------------- */
        document.querySelectorAll(".demo-chip").forEach(function (chip) {
            chip.addEventListener("click", function () {
                var u = document.getElementById("id_username");
                var p = document.getElementById("id_password");
                if (u && p) {
                    u.value = chip.dataset.username;
                    p.value = chip.dataset.password;
                    u.focus();
                    chip.classList.add("active");
                    setTimeout(function () { chip.classList.remove("active"); }, 300);
                }
            });
        });
    });
})();
