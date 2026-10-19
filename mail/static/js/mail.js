/* ============================================================
   W47: UI почты — JS.
   Этап 3: AJAX-загрузка письма (панель 3), клики по списку.
   ============================================================ */

(function () {
    'use strict';

    // === Утилита: CSRF-токен (задел) ===
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // === Селекторы ===
    const SEL_LIST_ITEM = '.mail-list-item';
    const SEL_VIEW = '.mail-panel-view';

    // === Получить панель 3 ===
    function getViewPanel() {
        return document.querySelector(SEL_VIEW);
    }

    // === Показать спиннер загрузки в панели 3 ===
    function showLoading() {
        const panel = getViewPanel();
        if (!panel) return;
        panel.innerHTML = `
            <div class="mail-loading">
                <div class="mail-loading-spinner"></div>
                <div>Загрузка письма…</div>
            </div>
        `;
    }

    // === Показать ошибку в панели 3 ===
    function showError(message) {
        const panel = getViewPanel();
        if (!panel) return;
        panel.innerHTML = `
            <div class="mail-load-error">
                <i class="bi bi-exclamation-triangle"></i>
                <div>${message || 'Не удалось загрузить письмо'}</div>
            </div>
        `;
    }

    // === Подсветить активное письмо в списке ===
    function setActiveItem(uid) {
        document.querySelectorAll(SEL_LIST_ITEM).forEach((el) => {
            el.classList.remove('is-active');
            if (String(el.dataset.uid) === String(uid)) {
                el.classList.add('is-active');
                // Убрать "непрочитанное" — мы только что прочитали
                el.classList.remove('is-unread');
            }
        });
    }

    // === Загрузить письмо через AJAX ===
    function loadMessage(uid, folder, pushState) {
        showLoading();

        const url = `/api/message/${uid}?folder=${encodeURIComponent(folder)}`;

        fetch(url, {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
        })
            .then((resp) => {
                if (!resp.ok) {
                    return resp.json().then((data) => {
                        throw new Error(data.error || `HTTP ${resp.status}`);
                    }).catch(() => {
                        throw new Error(`HTTP ${resp.status}`);
                    });
                }
                return resp.json();
            })
            .then((data) => {
                if (!data.ok) {
                    showError(data.error || 'Ошибка загрузки');
                    return;
                }

                const panel = getViewPanel();
                if (panel) {
                    panel.innerHTML = data.html;
                }

                setActiveItem(uid);

                if (pushState !== false) {
                    const newUrl = `/message/${uid}?folder=${encodeURIComponent(folder)}`;
                    history.pushState({ uid: uid, folder: folder }, '', newUrl);
                }
            })
            .catch((err) => {
                console.error('[mail.js] loadMessage error:', err);
                showError(err.message || 'Ошибка сети');
            });
    }

    // === Перехват кликов по письмам ===
    function initMessageList() {
        document.addEventListener('click', (e) => {
            const item = e.target.closest(SEL_LIST_ITEM);
            if (!item) return;

            // Не перехватываем клики по чекбоксу и звезде
            if (e.target.closest('.mail-list-checkbox') || e.target.closest('.mail-list-star')) {
                return;
            }

            e.preventDefault();

            const uid = item.dataset.uid;
            if (!uid) return;

            // Папку берём из data-folder у родителя или из URL
            const url = new URL(window.location.href);
            const folder = url.searchParams.get('folder') || 'INBOX';

            loadMessage(uid, folder, true);
        });
    }

    // === Обработка back/forward ===
    function initPopState() {
        window.addEventListener('popstate', (e) => {
            const state = e.state;
            if (state && state.uid) {
                loadMessage(state.uid, state.folder || 'INBOX', false);
            }
        });
    }

    // === Горячие клавиши (задел) ===
    function initHotkeys() {
        document.addEventListener('keydown', (e) => {
            const tag = (e.target && e.target.tagName) || '';
            if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) {
                return;
            }

            if (e.key === 'c') {
                const btn = document.querySelector('a[href*="/compose"]');
                if (btn) {
                    e.preventDefault();
                    btn.click();
                }
            }
        });
    }

    // === Экспорт ===
    window.MailApp = {
        getCsrfToken: getCsrfToken,
        loadMessage: loadMessage,
    };

    // === Запуск ===
    function init() {
        initMessageList();
        initPopState();
        initHotkeys();
        console.log('[mail.js] init complete (Этап 3)');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();