/* ============================================================
   W47: UI почты — базовый JS.
   Этап 1: инициализация, заглушки.
   Этапы 3–4: AJAX-навигация, compose, IMAP.
   ============================================================ */

(function () {
    'use strict';

    // === Утилита: получить CSRF-токен из meta (если есть) ===
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // === Инициализация кликов по папкам (пока обычные ссылки) ===
    function initFolders() {
        const items = document.querySelectorAll('.mail-folder-item');
        items.forEach((el) => {
            el.addEventListener('click', (e) => {
                // Этап 1: переход по ссылке как обычно.
                // Этап 3: AJAX-загрузка списка писем.
            });
        });
    }

    // === Инициализация кликов по письмам (пока ничего) ===
    function initMessageList() {
        const items = document.querySelectorAll('.mail-list-item');
        items.forEach((el) => {
            el.addEventListener('click', (e) => {
                // Этап 3: открытие письма в правой панели.
            });
        });
    }

    // === Горячие клавиши (задел) ===
    function initHotkeys() {
        document.addEventListener('keydown', (e) => {
            // Игнор, если фокус в input/textarea
            const tag = (e.target && e.target.tagName) || '';
            if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) {
                return;
            }

            // 'c' — compose (Gmail-style)
            if (e.key === 'c') {
                const btn = document.querySelector('a[href*="/compose"]');
                if (btn) {
                    e.preventDefault();
                    btn.click();
                }
            }
        });
    }

    // === Экспорт (для будущего использования) ===
    window.MailApp = {
        getCsrfToken: getCsrfToken,
    };

    // === Запуск ===
    function init() {
        initFolders();
        initMessageList();
        initHotkeys();
        console.log('[mail.js] init complete (Этап 1)');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();