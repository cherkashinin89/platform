/* ============================================================
   W47: Sieve-правила — сохранение, редактирование, удаление.
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        function getCsrf() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) return meta.getAttribute('content');
            const input = document.querySelector('input[name="csrf_token"]');
            return input ? input.value : '';
        }

        // === Форма (создание / редактирование) ===
        const form = document.getElementById('ruleForm');
        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();

                const ruleId = document.getElementById('ruleId').value;

                const data = {
                    id: ruleId ? parseInt(ruleId, 10) : null,
                    name: document.getElementById('ruleName').value.trim(),
                    conditions: {
                        from: document.getElementById('ruleFrom').value.trim(),
                        subject: document.getElementById('ruleSubject').value.trim(),
                        body: document.getElementById('ruleBody').value.trim(),
                    },
                    actions: {
                        move_to: document.getElementById('ruleMoveTo').value.trim(),
                        mark_read: document.getElementById('ruleMarkRead').checked,
                        delete: document.getElementById('ruleDelete').checked,
                    },
                    is_active: true,
                };

                fetch('/api/sieve/rule', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrf(),
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(data),
                })
                .then(r => r.json())
                .then(res => {
                    if (res.ok) location.reload();
                    else alert('Ошибка: ' + (res.error || 'неизвестная'));
                })
                .catch(err => alert('Ошибка сети: ' + err));
            });
        }

        // === Кнопки: редактировать / активировать / удалить ===
        document.addEventListener('click', function (e) {
            const btn = e.target.closest('button[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;

            if (action === 'edit') {
                const id = btn.dataset.id;
                const name = btn.dataset.name;
                const conditions = JSON.parse(btn.dataset.conditions || '{}');
                const actions = JSON.parse(btn.dataset.actions || '{}');

                document.getElementById('ruleId').value = id;
                document.getElementById('ruleName').value = name;
                document.getElementById('ruleFrom').value = conditions.from || '';
                document.getElementById('ruleSubject').value = conditions.subject || '';
                document.getElementById('ruleBody').value = conditions.body || '';
                document.getElementById('ruleMoveTo').value = actions.move_to || '';
                document.getElementById('ruleMarkRead').checked = !!actions.mark_read;
                document.getElementById('ruleDelete').checked = !!actions.delete;

                document.querySelector('#ruleModal .modal-title').textContent = 'Редактировать правило';
                new bootstrap.Modal(document.getElementById('ruleModal')).show();
            }

            if (action === 'activate') {
                const name = btn.dataset.name;
                fetch('/api/sieve/activate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrf(),
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ name: name }),
                })
                .then(r => r.json())
                .then(res => {
                    if (res.ok) location.reload();
                    else alert('Ошибка: ' + (res.error || 'неизвестная'));
                })
                .catch(err => alert('Ошибка сети: ' + err));
            }

            if (action === 'delete') {
                if (!confirm('Удалить правило?')) return;
                const id = btn.dataset.id;
                fetch(`/api/sieve/rule/${id}`, {
                    method: 'DELETE',
                    headers: { 'X-CSRFToken': getCsrf() },
                    credentials: 'same-origin',
                })
                .then(r => r.json())
                .then(res => {
                    if (res.ok) location.reload();
                    else alert('Ошибка: ' + (res.error || 'неизвестная'));
                })
                .catch(err => alert('Ошибка сети: ' + err));
            }
        });

    });

})();