/* ============================================================
   W47: Compose — инициализация TinyMCE и автодополнение.
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // === TinyMCE ===
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

        // === Автодополнение получателей ===
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
                        .catch(() => {
                            dropdown.style.display = 'none';
                        });
                }, 200);
            });

            document.addEventListener('click', (e) => {
                if (!wrapper.contains(e.target)) {
                    dropdown.style.display = 'none';
                }
            });
        });

        console.log('[compose] init complete');
    });

})();