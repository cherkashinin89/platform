/**
 * W59: просмотр офисных файлов (Collabora, read-only) в модалке.
 *
 * Перехватывает клик по плитке .attached-file[href^="/files/"]
 * с офисным расширением (.docx/.xlsx/.pptx), открывает модалку с iframe.
 */
(function () {
    'use strict';

    const OFFICE_EXT = ['docx', 'xlsx', 'pptx'];

    function getExt(href) {
        const m = href.match(/\.([a-z0-9]+)(?:[?#]|$)/i);
        if (m) return m[1].toLowerCase();
        // Если в href нет расширения (у нас /files/1 — без ext),
        // берём из имени (data-name или текста)
        return null;
    }

    function isOfficeFile(link) {
        // Проверяем по href (если есть ext) или по тексту (span.attached-file-name)
        const href = link.getAttribute('href') || '';
        let ext = getExt(href);
        if (!ext) {
            const nameEl = link.querySelector('.attached-file-name');
            if (nameEl) {
                const name = nameEl.textContent.trim();
                ext = (name.split('.').pop() || '').toLowerCase();
            }
        }
        return OFFICE_EXT.includes(ext);
    }

    function createModal() {
        // Если модалка уже есть — вернуть
        let modal = document.getElementById('fileViewerModal');
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = 'fileViewerModal';
        modal.className = 'modal fade';
        modal.tabIndex = -1;
        modal.innerHTML = `
            <div class="modal-dialog modal-fullscreen m-0 p-0">
                <div class="modal-content h-100 border-0">
                    <div class="modal-header py-1">
                        <h6 class="modal-title">Просмотр файла</h6>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body p-0" id="fileViewerBody" style="height: calc(100vh - 50px);">
                        <div class="text-center text-muted p-5">Загрузка...</div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }

    async function openViewer(fileId) {
        const modal = createModal();
        const body = document.getElementById('fileViewerBody');
        body.innerHTML = '<div class="text-center text-muted p-5">Загрузка...</div>';

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // При закрытии — удаляем iframe (освобождаем сессию Collabora)
        modal.addEventListener('hidden.bs.modal', function () {
            body.innerHTML = '';
        }, { once: true });

        try {
            const resp = await fetch(`/view/${fileId}`, { credentials: 'include' });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                body.innerHTML = `<div class="alert alert-danger m-3">${err.error || 'Ошибка загрузки'}</div>`;
                return;
            }
            const data = await resp.json();
            if (!data.ok) {
                body.innerHTML = `<div class="alert alert-danger m-3">${data.error || 'Ошибка'}</div>`;
                return;
            }

            const encodedWopiSrc = encodeURIComponent(data.wopi_src);
            const encodedToken = encodeURIComponent(data.access_token);
            const collaboraBase = data.collabora_url || 'http://192.168.2.19:5005';
            const src = `${collaboraBase}/browser/dist/cool.html?WOPISrc=${encodedWopiSrc}&access_token=${encodedToken}`;
            body.innerHTML = `<iframe src="${src}" style="width:100%;height:100%;border:none;display:block;"></iframe>`;

            // W59: перехватываем сообщения Collabora (Iframe_Height) и принудительно ставим 100vh
            const iframe = body.querySelector('iframe');
            window.addEventListener('message', function (e) {
                if (!e.data) return;
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.MessageId === 'Iframe_Height') {
                        // Игнорируем высоту от Collabora — ставим свою
                        iframe.style.height = '100%';
                    }
                } catch (err) {}
            });
        } catch (e) {
            console.error('file-viewer error:', e);
            body.innerHTML = `<div class="alert alert-danger m-3">Ошибка сети: ${e.message}</div>`;
        }
    }

    // Делегирование клика по документу
    document.addEventListener('click', function (e) {
        const link = e.target.closest('.attached-file[href^="/files/"]');
        if (!link) return;
        if (!isOfficeFile(link)) return;

        // Берём file_id из href: /files/123
        const m = link.getAttribute('href').match(/\/files\/(\d+)/);
        if (!m) return;

        e.preventDefault();
        openViewer(m[1]);
    });

    console.log('file-viewer.js: инициализирован');
})();