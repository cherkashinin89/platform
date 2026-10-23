/* ============================================================
   W47: Compose — TinyMCE, автодополнение, автосохранение.
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
                toolbar: 'undo redo | bold italic underline | bullist numlist | link | code',
                relative_urls: false,
                remove_script_host: false,
                convert_urls: false,
                branding: false,
                language: 'ru',
                setup: function (editor) {
                    editor.on('init', function () {
                        const initialBody = document.getElementById('composeBody').value;
                        if (initialBody) {
                            editor.setContent(initialBody);
                        }
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

            // CSRF-токен из формы
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
            // Отслеживаем изменения
            ['composeTo', 'composeCc', 'composeBcc', 'composeSubject'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.addEventListener('input', () => { dirty = true; });
            });

            if (typeof tinymce !== 'undefined') {
                tinymce.on('AddEditor', function (e) {
                    e.editor.on('input change undo redo', () => { dirty = true; });
                });
            }

            // Автосохранение каждые 30 сек
            setInterval(() => { if (dirty) saveDraft(); }, 30000);

            // При закрытии
            window.addEventListener('beforeunload', () => { if (dirty) saveDraft(); });

            // Кнопка "Сохранить черновик"
            const draftBtn = document.getElementById('composeDraft');
            if (draftBtn) {
                draftBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    saveDraft();
                });
            }
        }

        console.log('[compose] init complete');
    });

})();