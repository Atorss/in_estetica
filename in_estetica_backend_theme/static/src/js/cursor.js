/** @odoo-module **/
// Cursor custom platinado para el backend de Odoo (decorativo,
// no oculta el cursor nativo del navegador para no romper inputs).

(function () {
    'use strict';

    var booted = false;
    var isFinePointer = window.matchMedia && window.matchMedia('(pointer: fine)').matches;

    function boot() {
        if (booted || !isFinePointer) return;
        if (document.querySelector('.wobbe-cursor')) return;
        booted = true;

        var cursor = document.createElement('div');
        cursor.className = 'wobbe-cursor';
        var dot = document.createElement('div');
        dot.className = 'wobbe-cursor__dot';
        document.body.appendChild(cursor);
        document.body.appendChild(dot);
        document.body.classList.add('wobbe-cursor-on');

        var mx = window.innerWidth / 2, my = window.innerHeight / 2;
        var cx = mx, cy = my;

        document.addEventListener('mousemove', function (e) {
            mx = e.clientX;
            my = e.clientY;
            dot.style.transform = 'translate(' + (mx - 3) + 'px, ' + (my - 3) + 'px)';
        });

        function loop() {
            cx += (mx - cx) * 0.2;
            cy += (my - cy) * 0.2;
            cursor.style.transform = 'translate(' + (cx - 14) + 'px, ' + (cy - 14) + 'px)';
            requestAnimationFrame(loop);
        }
        loop();

        var hoverSelector = 'a, button, .btn, .o_menu_brand, .o_menu_sections > *, ' +
            '.o_kanban_record, .o_data_row, .o_searchview, .dropdown-item, ' +
            '.mk_apps_sidebar_menu li, .breadcrumb-item, .nav-link, ' +
            '.o_field_widget input, .o_field_widget textarea, .o_field_widget select, ' +
            '.o_form_button_create, .o_list_button_add';

        document.body.addEventListener('mouseover', function (e) {
            if (e.target.closest(hoverSelector)) cursor.classList.add('is-hover');
        });
        document.body.addEventListener('mouseout', function (e) {
            if (e.target.closest(hoverSelector)) cursor.classList.remove('is-hover');
        });
        document.addEventListener('mouseleave', function () {
            cursor.style.opacity = '0'; dot.style.opacity = '0';
        });
        document.addEventListener('mouseenter', function () {
            cursor.style.opacity = '1'; dot.style.opacity = '1';
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        setTimeout(boot, 200);
    }
    window.addEventListener('load', function () { setTimeout(boot, 400); });
})();
