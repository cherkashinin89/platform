/* ============================================================
   W47: Compose — инициализация TinyMCE и отправка.
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        if (typeof tinymce === 'undefined') {
            console.error('[compose] TinyMCE не загружен');
            return;
        }

        tinymce.init({
            selector: '#composeBody',
            license_key: 'gpl',   // <-- ДОБАВИТЬ ЭТУ СТРОКУ
            height: 400,
            menubar: false,
            plugins: 'link lists code',
            toolbar: 'undo redo | bold italic underline | bullist numlist | link | code',
            relative_urls: false,
            remove_script_host: false,
            convert_urls: false,
            branding: false,
            language: 'ru',
        });

        console.log('[compose] init complete');
    });

})();