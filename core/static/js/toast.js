/* ================================================================
   W31: Toast-уведомления — правый-верхний угол, стек.

   Использование: showToast('Текст', 'success', 4000)
   Тип: success | danger | warning | info (по умолчанию info)
   ================================================================ */

(function () {
    'use strict';

    const ICONS = {
        success: 'bi-check-circle-fill',
        danger:  'bi-x-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info:    'bi-info-circle-fill',
    };

    function ensureContainer() {
        let c = document.querySelector('.app-toast-container');
        if (!c) {
            c = document.createElement('div');
            c.className = 'app-toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    window.showToast = function (message, type, duration) {
        type = (type && type in ICONS) ? type : 'info';
        if (!duration || duration <= 0) {
            duration = (type === 'danger') ? 6000 : 4000;
        }

        const container = ensureContainer();

        const toast = document.createElement('div');
        toast.className = 'app-toast app-toast-' + type;

        const iconClass = ICONS[type];

        toast.innerHTML = `
            <div class="app-toast-icon"><i class="bi ${iconClass}"></i></div>
            <div class="app-toast-body">
                <div class="app-toast-message"></div>
            </div>
            <button type="button" class="app-toast-close-x" aria-label="Закрыть">✕</button>
        `;

        toast.querySelector('.app-toast-message').textContent = message;

        container.appendChild(toast);

        // Fade-in
        requestAnimationFrame(function () {
            toast.classList.add('is-visible');
        });

        let hideTimer = null;

        function hide() {
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
            toast.classList.add('is-hiding');
            toast.classList.remove('is-visible');
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);

                if (container.children.length === 0 && container.parentNode) {
                    container.parentNode.removeChild(container);
                }
            }, 300);
        }

        // Кнопка-крестик
        toast.querySelector('.app-toast-close-x').addEventListener('click', function (e) {
            e.stopPropagation();
            hide();
        });

        // Клик по тосту
        toast.addEventListener('click', hide);

        // Автозакрытие
        hideTimer = setTimeout(hide, duration);
    };
})();