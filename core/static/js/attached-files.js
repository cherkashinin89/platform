/* ================================================================
   W3: Модалка выбора файлов из облака + вставка плиток в TinyMCE
   ================================================================ */

(function () {
    'use strict';

    // ============ СОСТОЯНИЕ ============
    const state = {
        currentFolderId: null,        // id текущей папки (null = корень)
        selected: new Map(),          // Map<fileId, fileData> — выбранные
        foldersCache: [],             // плоский список папок (для дерева)
        expandedIds: new Set(),       // раскрытые узлы дерева
    };

    // ============ ЭЛЕМЕНТЫ DOM ============
    const el = {};

    function cacheElements() {
        el.overlay = document.getElementById('fmOverlay');
        el.close = document.getElementById('fmClose');
        el.treeRoot = document.getElementById('fmTreeRoot');
        el.treeContainer = document.getElementById('fmTreeContainer');
        el.tiles = document.getElementById('fmTiles');
        el.selectedCount = document.getElementById('fmSelectedCount');
        el.totalCount = document.getElementById('fmTotalCount');
        el.attachCount = document.getElementById('fmAttachCount');
        el.attachBtn = document.getElementById('fmAttachBtn');
        el.selectAll = document.getElementById('fmSelectAll');
        el.clearAll = document.getElementById('fmClearAll');
    }

    // ============ CSRF ============
    function getCsrf() {
        const input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : '';
    }

    // ============ ОТКРЫТИЕ / ЗАКРЫТИЕ ============
    window.fmOpen = function () {
        if (!el.overlay) {
            console.error('fmOpen: overlay не найден (партиал не подключён?)');
            return;
        }
        // Сброс состояния при открытии
        state.selected.clear();
        state.currentFolderId = null;
        updateCounter();
        renderTilesEmpty('Загрузка…');

        el.overlay.classList.add('is-open');
        el.overlay.setAttribute('aria-hidden', 'false');

        // Загружаем дерево и корень
        loadTree();
        loadFolder(null);
    };

    function closeModal() {
        if (!el.overlay) return;
        el.overlay.classList.remove('is-open');
        el.overlay.setAttribute('aria-hidden', 'true');
    }

    // ============ ДЕРЕВО ============
    async function loadTree() {
        try {
            const resp = await fetch('/admin/api/cloud-tree', {
                credentials: 'same-origin',
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            state.foldersCache = await resp.json();
            renderTree();
        } catch (e) {
            console.error('loadTree error:', e);
            if (el.treeContainer) {
                el.treeContainer.innerHTML = '<div class="text-muted small p-2">Ошибка загрузки дерева</div>';
            }
        }
    }

    function renderTree() {
        if (!el.treeContainer) return;
        el.treeContainer.innerHTML = '';

        // Строим Map<parent_id, children[]>
        const byParent = new Map();
        for (const f of state.foldersCache) {
            const key = f.parent_id === null ? '__root__' : f.parent_id;
            if (!byParent.has(key)) byParent.set(key, []);
            byParent.get(key).push(f);
        }

        const renderNodes = (parentKey, depth) => {
            const children = byParent.get(parentKey) || [];
            for (const node of children) {
                const hasChildren = byParent.has(node.id) && byParent.get(node.id).length > 0;
                const isExpanded = state.expandedIds.has(node.id);
                const isActive = state.currentFolderId === node.id;
                const indent = 12 + depth * 14;

                const div = document.createElement('div');
                div.className = 'fm-tree-node' + (isActive ? ' is-active' : '');
                div.style.paddingLeft = indent + 'px';
                div.dataset.folderId = node.id;

                let toggleHtml = '<span class="fm-tree-spacer"></span>';
                if (hasChildren) {
                    toggleHtml = `<span class="fm-tree-toggle">${isExpanded ? '▼' : '▶'}</span>`;
                }

                div.innerHTML = `
                    ${toggleHtml}
                    <i class="bi bi-folder-fill"></i>
                    <span>${escapeHtml(node.name)}</span>
                `;

                // Клик по стрелке — раскрыть/свернуть
                const toggle = div.querySelector('.fm-tree-toggle');
                if (toggle) {
                    toggle.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (state.expandedIds.has(node.id)) {
                            state.expandedIds.delete(node.id);
                        } else {
                            state.expandedIds.add(node.id);
                        }
                        renderTree();
                    });
                }

                // Клик по узлу — открыть папку
                div.addEventListener('click', () => {
                    state.currentFolderId = node.id;
                    state.expandedIds.add(node.id);
                    loadFolder(node.id);
                    renderTree();
                });

                el.treeContainer.appendChild(div);

                if (hasChildren && isExpanded) {
                    renderNodes(node.id, depth + 1);
                }
            }
        };

        renderNodes('__root__', 0);
    }

    // ============ ЗАГРУЗКА СОДЕРЖИМОГО ПАПКИ ============
    async function loadFolder(folderId) {
        state.currentFolderId = folderId;
        renderTilesEmpty('Загрузка…');

        // Подсветка корня в дереве
        if (el.treeRoot) {
            el.treeRoot.classList.toggle('is-active', folderId === null);
        }

        const url = folderId === null
            ? null
            : `/admin/api/cloud-folder/${folderId}`;

        try {
            let folders = [];
            let files = [];

            if (folderId === null) {
                // Корень: берём папки из дерева + файлы из cloud-files с parent_id=null
                folders = state.foldersCache.filter(f => f.parent_id === null);
                const resp = await fetch('/admin/api/cloud-files?type=all', { credentials: 'same-origin' });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const all = await resp.json();
                files = all.filter(f => !f.is_folder && f.parent_id === null);
            } else {
                const resp = await fetch(url, { credentials: 'same-origin' });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();
                folders = data.folders || [];
                files = data.files || [];
            }

            renderTiles(folders, files);
        } catch (e) {
            console.error('loadFolder error:', e);
            renderTilesEmpty('Ошибка загрузки');
        }
    }

    // ============ РЕНДЕР ПЛИТОК ============
    function renderTilesEmpty(text) {
        if (!el.tiles) return;
        el.tiles.innerHTML = `<div class="fm-tiles-empty">${escapeHtml(text)}</div>`;
        if (el.totalCount) el.totalCount.textContent = '0';
    }

    function renderTiles(folders, files) {
        if (!el.tiles) return;
        el.tiles.innerHTML = '';

        const total = (folders ? folders.length : 0) + (files ? files.length : 0);
        if (el.totalCount) el.totalCount.textContent = String(total);

        if (total === 0) {
            renderTilesEmpty('Папка пуста');
            return;
        }

        // Папки первыми
        if (folders) {
            for (const f of folders) {
                el.tiles.appendChild(makeFolderTile(f));
            }
        }
        // Затем файлы
        if (files) {
            for (const f of files) {
                el.tiles.appendChild(makeFileTile(f));
            }
        }
    }

    function makeFolderTile(folder) {
        const div = document.createElement('div');
        div.className = 'fm-tile is-folder';
        div.dataset.folderId = folder.id;

        const icon = 'bi-folder-fill';

        div.innerHTML = `
            <div class="fm-tile-preview"><i class="bi ${icon}"></i></div>
            <div class="fm-tile-name">${escapeHtml(folder.name)}</div>
            <div class="fm-tile-size">папка</div>
            <div class="fm-tile-checkbox" data-action="select"></div>
        `;

        // Клик по чекбоксу — выбрать папку
        div.querySelector('.fm-tile-checkbox').addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSelect({
                id: 'folder:' + folder.id,
                type: 'folder',
                file_id: folder.id,
                name: folder.name,
                is_folder: true,
                size: null,
            });
            div.classList.toggle('is-selected');
        });

        // Клик по плитке (кроме чекбокса) — войти в папку
        div.addEventListener('click', () => {
            state.currentFolderId = folder.id;
            state.expandedIds.add(folder.id);
            loadFolder(folder.id);
            renderTree();
        });

        return div;
    }

    function makeFileTile(file) {
        const div = document.createElement('div');
        div.className = 'fm-tile';
        div.dataset.fileId = file.id;

        const isImage = file.type === 'image' && file.thumbnail_url;
        const iconClass = getIconClass(file.type);
        const sizeText = file.size || '';

        let previewHtml;
        if (isImage) {
            previewHtml = `<img src="${file.thumbnail_url}" alt="${escapeAttr(file.name)}" loading="lazy">`;
        } else {
            previewHtml = `<i class="bi ${iconClass}"></i>`;
        }

        div.innerHTML = `
            <div class="fm-tile-preview">${previewHtml}</div>
            <div class="fm-tile-name">${escapeHtml(file.name)}</div>
            <div class="fm-tile-size">${escapeHtml(sizeText)}</div>
            <div class="fm-tile-checkbox" data-action="select"></div>
        `;

        // Клик по чекбоксу или по плитке — выбрать
        const toggle = () => {
            toggleSelect({
                id: 'file:' + file.id,
                type: 'file',
                file_id: file.id,
                name: file.name,
                is_folder: false,
                size: file.size,
                mime_type: file.type,      // category (image / document / ...)
            });
            div.classList.toggle('is-selected');
        };

        div.querySelector('.fm-tile-checkbox').addEventListener('click', (e) => {
            e.stopPropagation();
            toggle();
        });
        div.addEventListener('click', toggle);

        return div;
    }

    function getIconClass(type) {
        switch (type) {
            case 'image': return 'bi-file-earmark-image';
            case 'video': return 'bi-file-earmark-play';
            case 'audio': return 'bi-file-earmark-music';
            case 'archive': return 'bi-file-earmark-zip';
            case 'document': return 'bi-file-earmark-text';
            default: return 'bi-file-earmark';
        }
    }

    // ============ ВЫБОР ============
    function toggleSelect(item) {
        if (state.selected.has(item.id)) {
            state.selected.delete(item.id);
        } else {
            state.selected.set(item.id, item);
        }
        updateCounter();
    }

    function updateCounter() {
        const n = state.selected.size;
        if (el.selectedCount) el.selectedCount.textContent = String(n);
        if (el.attachCount) el.attachCount.textContent = String(n);
        if (el.attachBtn) el.attachBtn.disabled = n === 0;
    }

    // ============ ПРИКРЕПЛЕНИЕ ============
    async function attachSelected() {
        if (state.selected.size === 0) return;
        if (!window.__activeEditor) {
            alert('Не найден активный редактор');
            return;
        }

        // Определяем режим: create (нет id) или edit (есть id)
        const match = window.location.pathname.match(/\/admin\/(articles|pages)\/(\d+)/);
        const isCreateMode = !match;

        // Собираем выбранные элементы
        const selectedItems = Array.from(state.selected.values());
        const fileItems = selectedItems.filter(i => i.type === 'file');

        // Что делать с папками (пока не поддерживаются)
        const folderItems = selectedItems.filter(i => i.type === 'folder');
        const allItems = [...folderItems, ...fileItems];

        if (allItems.length === 0) return;

        if (fileItems.length > 20) {
            if (!confirm(`Выбрано ${fileItems.length} файлов. Продолжить?`)) return;
        }

        // === РЕЖИМ CREATE: вставляем data-file-id, без API ===
        if (isCreateMode) {
            const html = allItems.map(item => makeTempHtml(item)).join(' ');
            window.__activeEditor.insertContent(`<p>${html}</p>`);
            closeModal();
            return;
        }

        // === РЕЖИМ EDIT: создаём шары через API, вставляем data-share-token ===
        const targetType = match[1];   // 'articles' или 'pages'
        const targetId = parseInt(match[2]);

        const payload = {
            article_id: targetType === 'articles' ? targetId : null,
            page_id: targetType === 'pages' ? targetId : null,
            file_ids: allItems.map(i => i.file_id),
        };

        try {
            const resp = await fetch('/admin/api/attach-to-article', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrf(),
                },
                body: JSON.stringify(payload),
            });

            const text = await resp.text();
            let data;
            try { data = JSON.parse(text); } catch (e) {
                throw new Error('Некорректный JSON: ' + text.slice(0, 200));
            }

            if (!resp.ok || !data.ok) {
                alert('Ошибка: ' + (data.error || ('HTTP ' + resp.status)));
                return;
            }

            const html = data.attachments.map(makeAttachedHtml).join(' ');
            window.__activeEditor.insertContent(`<p>${html}</p>`);

            closeModal();
        } catch (e) {
            console.error('attach error:', e);
            alert('Ошибка прикрепления: ' + e.message);
        }
    }

    function makeTempHtml(item) {
        // Временная плитка: data-file-id + класс is-temp
        // Различаем папки и файлы

        if (item.type === 'folder') {
            // Папка: data-file-id + data-folder-id (для навигации после сохранения)
            return `<a class="attached-file attached-file-folder is-temp" href="#" data-file-id="${item.file_id}" data-folder-id="${item.file_id}" data-is-folder="true"><i class="bi bi-folder-fill"></i> <span class="attached-file-name">${escapeHtml(item.name)}</span></a>`;
        }

        const ext = (item.name.split('.').pop() || '').toLowerCase();
        const isImage = ['jpg','jpeg','png','gif','webp','bmp','svg'].includes(ext);
        const iconClass = getIconClassForExt(ext);

        if (isImage) {
            return `<a class="attached-file attached-file-image is-temp" data-file-id="${item.file_id}"><img src="/media/${item.file_id}" alt="${escapeAttr(item.name)}"></a>`;
        }
        return `<a class="attached-file is-temp" data-file-id="${item.file_id}"><i class="bi ${iconClass}"></i> <span class="attached-file-name">${escapeHtml(item.name)}</span></a>`;
    }

    function makeAttachedHtml(att) {
        const path = att.path;   // '/s/<token>'
        const name = att.file_name;

        if (att.is_folder) {
            return `<a class="attached-file attached-file-folder" href="#" data-share-token="${escapeAttr(att.token)}" data-folder-id="${att.file_id}" data-is-folder="true"><i class="bi bi-folder-fill"></i> <span class="attached-file-name">${escapeHtml(name)}</span></a>`;
        }
        // Файл — иконку подберём на клиенте (пока по расширению)
        const ext = (name.split('.').pop() || '').toLowerCase();
        const isImage = ['jpg','jpeg','png','gif','webp','bmp','svg'].includes(ext);
        if (isImage) {
            return `<a class="attached-file attached-file-image" href="${path}" data-share-token="${escapeAttr(att.token)}"><img src="/media/${att.file_id}" alt="${escapeAttr(name)}"></a>`;
        }
        return `<a class="attached-file" href="${path}" data-share-token="${escapeAttr(att.token)}"><i class="bi ${getIconClassForExt(ext)}"></i> <span class="attached-file-name">${escapeHtml(name)}</span></a>`;
    }

    function getIconClassForExt(ext) {
        if (['pdf'].includes(ext)) return 'bi-file-earmark-pdf';
        if (['doc','docx','rtf','odt'].includes(ext)) return 'bi-file-earmark-word';
        if (['xls','xlsx','csv','ods'].includes(ext)) return 'bi-file-earmark-excel';
        if (['ppt','pptx','odp'].includes(ext)) return 'bi-file-earmark-ppt';
        if (['zip','rar','7z','tar','gz','bz2'].includes(ext)) return 'bi-file-earmark-zip';
        if (['txt','md'].includes(ext)) return 'bi-file-earmark-text';
        return 'bi-file-earmark';
    }

    // ============ УТИЛИТЫ ============
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }
    function escapeAttr(s) { return escapeHtml(s); }

    // ============ ИНИЦИАЛИЗАЦИЯ ============
    document.addEventListener('DOMContentLoaded', function () {
        cacheElements();

        if (!el.overlay) {
            console.warn('attached-files.js: #fmOverlay не найден — модалка не подключена');
            return;
        }

        // Закрытие по крестику
        if (el.close) el.close.addEventListener('click', closeModal);
        // Закрытие по клику на оверлей (вне модалки)
        el.overlay.addEventListener('click', (e) => {
            if (e.target === el.overlay) closeModal();
        });

        // Клик по корню дерева
        if (el.treeRoot) {
            el.treeRoot.addEventListener('click', () => {
                state.currentFolderId = null;
                loadFolder(null);
                renderTree();
            });
        }

        // Выбрать все (на текущей странице — только файлы)
        if (el.selectAll) {
            el.selectAll.addEventListener('click', () => {
                document.querySelectorAll('.fm-tile:not(.is-folder)').forEach(t => {
                    if (!t.classList.contains('is-selected')) t.click();
                });
            });
        }
        // Снять все
        if (el.clearAll) {
            el.clearAll.addEventListener('click', () => {
                state.selected.clear();
                document.querySelectorAll('.fm-tile.is-selected').forEach(t => t.classList.remove('is-selected'));
                updateCounter();
            });
        }

        // Кнопка «Прикрепить»
        if (el.attachBtn) el.attachBtn.addEventListener('click', attachSelected);

        console.log('attached-files.js: инициализирован');
    });

        // ============ W3: НАВИГАЦИЯ ПО ПАПКАМ В СТАТЬЕ ============
    function initArticleFolderNavigation() {
        // Только на публичных страницах статьи (не в админке)
        if (window.location.pathname.startsWith('/admin/')) return;

        // Клик по плитке папки в статье
        document.addEventListener('click', function (e) {
            const folderLink = e.target.closest('.attached-file-folder[data-share-token]');
            if (!folderLink) return;

            // Не перехватываем, если уже открыт folder-view
            if (document.querySelector('.folder-view')) return;

            e.preventDefault();

            const token = folderLink.getAttribute('data-share-token');
            const folderId = folderLink.getAttribute('data-folder-id');

            // folder_id у плитки нет в текущей верстке — вычислим по контексту.
            // Плитка папки имеет только data-share-token, значит это корень шары.
            // Определяем article_id из URL: /article/<id>
            const match = window.location.pathname.match(/\/article\/(\d+)/);
            if (!match) return;
            const articleId = match[1];

            // Находим id корня папки-шары. К сожалению, в HTML его нет.
            // Проще: сделать запрос на /s/<token>?folder=<root> — но у нас нет root_id.
            // Поэтому плитка папки должна иметь data-folder-id в HTML.
            // См. обновление шаблона плитки папки: см. attached_file.html (TODO).
            // Пока — используем data-folder-id, если он есть.
            const rootFolderId = folderLink.getAttribute('data-folder-id');
            if (!rootFolderId) {
                console.warn('attached-file-folder без data-folder-id');
                return;
            }

            openFolderView(articleId, rootFolderId);
        });

        // Делегирование: клик по кнопкам внутри folder-view
        document.addEventListener('click', function (e) {
            // Кнопка "Крестик" — закрыть
            if (e.target.closest('#fvClose')) {
                e.preventDefault();
                closeFolderView();
                return;
            }

            // Кнопка "Назад" — на уровень выше
            if (e.target.closest('#fvBack')) {
                e.preventDefault();
                const fv = document.querySelector('.folder-view');
                if (!fv) return;
                const currentFolderId = fv.getAttribute('data-folder-id');
                const token = fv.getAttribute('data-token');
                // Запрашиваем содержимое, но нам нужен parent. К сожалению, мы его не знаем.
                // Просто перезагружаем корень папки-шары.
                const articleId = window.location.pathname.match(/\/article\/(\d+)/)?.[1];
                if (articleId && token) {
                    // Пока «Назад» ведёт в корень. Полноценная навигация — позже.
                    const rootId = fv.getAttribute('data-item-id');
                    if (rootId) openFolderView(articleId, rootId);
                }
                return;
            }

            // Клик по подпапке внутри folder-view
            const subFolder = e.target.closest('.folder-view-folder[data-folder-id]');
            if (subFolder) {
                e.preventDefault();
                const articleId = window.location.pathname.match(/\/article\/(\d+)/)?.[1];
                if (!articleId) return;
                const folderId = subFolder.getAttribute('data-folder-id');
                openFolderView(articleId, folderId);
                return;
            }
        });
    }

    function openFolderView(articleId, folderId) {
        const articleContent = document.querySelector('.article-content');
        if (!articleContent) return;

        // Скрываем текст статьи
        articleContent.style.display = 'none';

        // Контейнер для фрагмента — после article-content
        let container = document.getElementById('folderViewContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'folderViewContainer';
            articleContent.parentNode.insertBefore(container, articleContent.nextSibling);
        }

        container.innerHTML = '<div class="text-muted text-center py-3">Загрузка…</div>';

        fetch(`/article/${articleId}/folder/${folderId}`, { credentials: 'same-origin' })
            .then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.text();
            })
            .then(html => {
                container.innerHTML = html;
            })
            .catch(e => {
                console.error('folder view error:', e);
                container.innerHTML = '<div class="text-danger text-center py-3">Не удалось загрузить папку</div>';
            });
    }

    function closeFolderView() {
        const articleContent = document.querySelector('.article-content');
        const container = document.getElementById('folderViewContainer');
        if (articleContent) articleContent.style.display = '';
        if (container) container.innerHTML = '';
    }

    document.addEventListener('DOMContentLoaded', function () {
        initArticleFolderNavigation();
    });

})();