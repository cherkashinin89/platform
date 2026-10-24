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

            // Папку берём из data-folder у элемента или из URL
            let folder = item.dataset.folder;
            if (!folder) {
                const url = new URL(window.location.href);
                folder = url.searchParams.get('folder') || 'INBOX';
            }

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

    // === Поиск ===
    const searchForm = document.getElementById('mailSearchForm');
    const searchInput = document.getElementById('mailSearchInput');
    const searchClear = document.getElementById('mailSearchClear');

    if (searchForm) {
        searchForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const q = searchInput.value.trim();
            if (!q) return;

            fetch(`/api/search?q=${encodeURIComponent(q)}&folder=INBOX`)
                .then(r => r.json())
                .then(data => {
                    if (!data.ok) {
                        alert('Ошибка поиска: ' + (data.error || 'неизвестная'));
                        return;
                    }
                    renderSearchResults(data.results);
                })
                .catch(err => alert('Ошибка сети: ' + err));
        });

        searchClear.addEventListener('click', function () {
            searchInput.value = '';
            // Перезагрузить INBOX
            window.location.href = '/inbox';
        });
    }

    function renderSearchResults(results) {
        const list = document.querySelector('.mail-list-body');
        if (!list) return;
        list.innerHTML = '';
        if (!results.length) {
            list.innerHTML = '<div class="mail-empty"><i class="bi bi-search"></i><div>Ничего не найдено</div></div>';
            return;
        }
        results.forEach(msg => {
            const a = document.createElement('a');
            a.href = `/message/${msg.uid}?folder=INBOX`;
            a.className = 'mail-list-item' + (msg.is_read ? '' : ' is-unread');
            a.dataset.uid = msg.uid;
            a.dataset.folder = 'INBOX';
            a.innerHTML = `
                <div class="mail-list-checkbox"></div>
                <div class="mail-list-star"><i class="bi ${msg.is_flagged ? 'bi-star-fill' : 'bi-star'}"></i></div>
                <div class="mail-list-content">
                    <div class="mail-list-from">${msg.from_name || msg.from_email}</div>
                    <div class="mail-list-subject">${msg.subject}</div>
                </div>
                <div class="mail-list-date">${msg.date_human}</div>
            `;
            list.appendChild(a);
        });
    }

    // === Создание папки ===
    const createFolderBtn = document.getElementById('createFolderBtn');
    if (createFolderBtn) {
        createFolderBtn.addEventListener('click', function () {
            const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
            modal.show();
        });
    }

    const createFolderConfirm = document.getElementById('createFolderConfirm');
    if (createFolderConfirm) {
        createFolderConfirm.addEventListener('click', function () {
            const name = document.getElementById('newFolderName').value.trim();
            if (!name) return;

            fetch('/api/folder/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ name: name }),
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    location.reload();
                } else {
                    alert('Ошибка: ' + (data.error || 'неизвестная'));
                }
            })
            .catch(err => alert('Ошибка сети: ' + err));
        });
    }
    
    // === Меню действий для папок ===
    document.addEventListener('click', function (e) {
        const menuBtn = e.target.closest('.mail-folder-menu-btn');
        if (!menuBtn) return;

        // Удалить старое меню
        document.querySelectorAll('.mail-folder-dropdown').forEach(m => m.remove());

        const folderName = menuBtn.dataset.folderName;
        const dropdown = document.createElement('div');
        dropdown.className = 'mail-folder-dropdown';
        dropdown.innerHTML = `
            <button data-action="rename">Переименовать</button>
            <button data-action="delete">Удалить</button>
        `;

        menuBtn.parentNode.appendChild(dropdown);

        dropdown.addEventListener('click', function (ev) {
            const action = ev.target.dataset.action;
            if (!action) return;

            dropdown.remove();

            if (action === 'rename') {
                const newName = prompt('Новое имя папки:', folderName);
                if (!newName || newName === folderName) return;
                fetch('/api/folder/rename', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ old_name: folderName, new_name: newName }),
                })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) location.reload();
                    else alert('Ошибка: ' + (data.error || 'неизвестная'));
                })
                .catch(err => alert('Ошибка сети: ' + err));
            }

            if (action === 'delete') {
                if (!confirm(`Удалить папку "${folderName}"?`)) return;
                fetch('/api/folder/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: folderName }),
                })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) location.reload();
                    else alert('Ошибка: ' + (data.error || 'неизвестная'));
                })
                .catch(err => alert('Ошибка сети: ' + err));
            }
        });
    });

    // === Удаление письма ===
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('#deleteMessageBtn');
        if (!btn) return;

        const uid = btn.dataset.uid;
        const folder = btn.dataset.folder;
        if (!uid) return;

        if (!confirm('Переместить письмо в корзину?')) return;

        fetch('/api/message/trash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ uid: uid, folder: folder }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                 // Успех — перезагружаем папку
                window.location.href = `/folder/${encodeURIComponent(folder)}`;
            } else {
                alert('Ошибка: ' + (data.error || 'неизвестная'));
            }
        })
        .catch(err => alert('Ошибка сети: ' + err));
    });

    // === Перемещение письма ===
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('#moveMessageBtn');
        if (!btn) return;

        const uid = btn.dataset.uid;
        const folder = btn.dataset.folder;
        if (!uid) return;

        // Заполняем select
        const modal = new bootstrap.Modal(document.getElementById('moveMessageModal'));
        modal.show();

        // Обработчик подтверждения (один раз)
        const confirmBtn = document.getElementById('moveMessageConfirm');
        confirmBtn.onclick = function () {
            const dest = document.getElementById('moveDestSelect').value;
            if (!dest) return;

            fetch('/api/message/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ uid: uid, folder: folder, dest: dest }),
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    modal.hide();
                    window.location.href = `/folder/${encodeURIComponent(folder)}`;
                } else {
                    alert('Ошибка: ' + (data.error || 'неизвестная'));
                }
            })
            .catch(err => alert('Ошибка сети: ' + err));
        };
    });

})();