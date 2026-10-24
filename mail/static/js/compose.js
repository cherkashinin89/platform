/* ============================================================
   W47: Compose — TinyMCE, автодополнение, автосохранение,
   кнопка "Из облака" (attachfile).
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        // === 1. TinyMCE ===
        if (typeof tinymce !== 'undefined') {
            tinymce.init({
                selector: '#composeBody',
                license_key: 'gpl',
                height: 400,
                menubar: false,
                plugins: 'link lists code',
                toolbar: 'undo redo | bold italic underline | bullist numlist | link | attachfile | code',
                relative_urls: false,
                remove_script_host: false,
                convert_urls: false,
                branding: false,
                language: 'ru',
                setup: function (editor) {
                    // prefill_body (ответ/пересылка)
                    editor.on('init', function () {
                        const initialBody = document.getElementById('composeBody').value;
                        if (initialBody) {
                            editor.setContent(initialBody);
                        }
                    });

                    // Кнопка "Из облака"
                    editor.ui.registry.addButton('attachfile', {
                        icon: 'upload',
                        tooltip: 'Прикрепить из облака',
                        onAction: function () {
                            window.__activeEditor = editor;
                            if (window.fmOpen) {
                                window.fmOpen();
                            } else {
                                console.error('fmOpen не найден');
                            }
                        }
                    });

                    editor.on('focus', function () {
                        window.__activeEditor = editor;
                    });
                },
            });
        } else {
            console.error('[compose] TinyMCE не загружен');
        }

        // === 2. Автодополнение получателей ===
        const inputs = ['composeTo', 'composeCc', 'composeBcc'];
        inputs.forEach(id => {
            const input = document.getElementById(id);
            if (!input) return;

            const wrapper = document.createElement('div');
            wrapper.className = 'recipient-suggest-wrapper';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);

            const dropdown = document.createElement('div');
            dropdown.className = 'recipient-suggest-dropdown';
            dropdown.style.display = 'none';
            wrapper.appendChild(dropdown);

            let timer = null;

            input.addEventListener('input', function () {
                clearTimeout(timer);
                const q = this.value.trim();
                if (q.length < 1) {
                    dropdown.style.display = 'none';
                    return;
                }
                timer = setTimeout(() => {
                    fetch(`/api/recipients?q=${encodeURIComponent(q)}`)
                        .then(r => r.json())
                        .then(data => {
                            if (!data.ok || !data.items.length) {
                                dropdown.style.display = 'none';
                                return;
                            }
                            dropdown.innerHTML = '';
                            data.items.forEach(item => {
                                const div = document.createElement('div');
                                div.className = 'recipient-suggest-item';
                                div.textContent = item.name
                                    ? `${item.name} <${item.email}>`
                                    : item.email;
                                div.addEventListener('click', () => {
                                    input.value = item.email;
                                    dropdown.style.display = 'none';
                                });
                                dropdown.appendChild(div);
                            });
                            dropdown.style.display = 'block';
                        })
                        .catch(() => { dropdown.style.display = 'none'; });
                }, 200);
            });

            document.addEventListener('click', (e) => {
                if (!wrapper.contains(e.target)) {
                    dropdown.style.display = 'none';
                }
            });
        });

        // === 3. Автосохранение черновика ===
        const draftForm = document.getElementById('composeForm');
        let dirty = false;

        function saveDraft() {
            const to = document.getElementById('composeTo').value;
            const subject = document.getElementById('composeSubject').value;
            let body = '';

            if (typeof tinymce !== 'undefined') {
                const editor = tinymce.get('composeBody');
                if (editor) body = editor.getContent();
            }
            if (!body) {
                body = document.getElementById('composeBody').value;
            }

            if (!to && !subject && !body) return;

            const csrfInput = document.querySelector('input[name="csrf_token"]');
            const csrfToken = csrfInput ? csrfInput.value : '';

            fetch('/api/draft', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                },
                credentials: 'same-origin',
                body: JSON.stringify({ to: to, subject: subject, body: body }),
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    dirty = false;
                    console.log('[compose] черновик сохранён');
                } else {
                    console.warn('[compose] ошибка сохранения черновика:', data.error);
                }
            })
            .catch(err => {
                console.warn('[compose] ошибка сети при сохранении черновика:', err);
            });
        }

        if (draftForm) {
            ['composeTo', 'composeCc', 'composeBcc', 'composeSubject'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.addEventListener('input', () => { dirty = true; });
            });

            if (typeof tinymce !== 'undefined') {
                tinymce.on('AddEditor', function (e) {
                    e.editor.on('input change undo redo', () => { dirty = true; });
                });
            }

            setInterval(() => { if (dirty) saveDraft(); }, 30000);

            window.addEventListener('beforeunload', () => { if (dirty) saveDraft(); });

            const draftBtn = document.getElementById('composeDraft');
            if (draftBtn) {
                draftBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    saveDraft();
                });
            }
        }

        // === 4. Отображение выбранных файлов ===
        const fileInput = document.getElementById('composeFile');
        const fileList = document.getElementById('composeFileList');

        if (fileInput && fileList) {
            fileInput.addEventListener('change', function () {
                fileList.innerHTML = '';
                Array.from(this.files).forEach((file, index) => {
                    const div = document.createElement('div');
                    div.className = 'mail-compose-file-item';
                    div.innerHTML = `
                        <i class="bi bi-file-earmark"></i>
                        <span class="mail-compose-file-name">${file.name}</span>
                        <span class="mail-compose-file-size">${(file.size / 1024).toFixed(1)} КБ</span>
                        <button type="button" class="btn btn-sm btn-link text-danger"
                                data-index="${index}">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    `;
                    div.querySelector('button').addEventListener('click', () => {
                        const dt = new DataTransfer();
                        Array.from(fileInput.files).forEach((f, i) => {
                            if (i !== index) dt.items.add(f);
                        });
                        fileInput.files = dt.files;
                        fileInput.dispatchEvent(new Event('change'));
                    });
                    fileList.appendChild(div);
                });
            });
        }

        // === Восстановление черновика ===
        const restoreModalEl = document.getElementById('restoreDraftModal');
        if (restoreModalEl && !window.location.search) {
            // Только если нет параметров (reply/forward)
            fetch('/api/latest-draft')
                .then(r => r.json())
                .then(data => {
                    if (!data.ok || data.none) return;
                    // Показываем модалку
                    document.getElementById('draftPreview').textContent =
                        `${data.subject || '(без темы)'} — ${data.date_human}`;
                    const modal = new bootstrap.Modal(restoreModalEl);
                    modal.show();

                    // "Восстановить"
                    document.getElementById('draftRestore').addEventListener('click', function () {
                        document.getElementById('composeTo').value = data.to || '';
                        document.getElementById('composeCc').value = data.cc || '';
                        document.getElementById('composeSubject').value = data.subject || '';
                        // Тело — в TinyMCE
                        if (typeof tinymce !== 'undefined') {
                            const editor = tinymce.get('composeBody');
                            if (editor) editor.setContent(data.body || '');
                        } else {
                            document.getElementById('composeBody').value = data.body || '';
                        }
                        modal.hide();
                    });

                    // "Удалить"
                    document.getElementById('draftDiscard').addEventListener('click', function () {
                        // Удаляем черновик через API (опционально)
                        modal.hide();
                    });
                })
                .catch(() => {});
        }

        console.log('[compose] init complete');
    });

})();