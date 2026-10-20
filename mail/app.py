# mail/app.py — mail-сервис (Flask)
import os
from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    jsonify, abort, current_app
)
from flask_login import login_required, current_user
from jinja2 import ChoiceLoader, FileSystemLoader

from config import Config

# === Общий пакет core ===
from core.extensions import db, login_manager, csrf, migrate, cache, limiter
from core.models import (
    User, MailDomain, Mailbox, SiteSettings,
    MailUiState, MailSettings,
)
from mail_service import hash_password, get_quota, reload_service, archive_mailbox

import imap_client


def create_app(config_class=Config):
    """Создаёт и настраивает экземпляр Flask (mail)."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Jinja-фильтры (общие из core)
    from core.file_utils import human_size
    app.jinja_env.filters['human_size_bytes'] = human_size
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Подключаем шаблоны core (общие) + локальные
    core_templates = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'core', 'templates'
    )
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(core_templates),
    ])

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    limiter.init_app(app)

    # === W47: CSP для защиты от XSS ===
    @app.after_request
    def add_security_headers(response):
        # Только для mail-сервиса — CSP, запрещающий inline-скрипты
        csp = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; "  # inline-стили разрешены (письма)
            "script-src 'self'; "                  # скрипты только локальные
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
        )
        response.headers['Content-Security-Policy'] = csp
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Загрузчик пользователя
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Обработчик «не авторизован» — редирект на framework-логин
    @login_manager.unauthorized_handler
    def unauthorized():
        try:
            settings = SiteSettings.get()
            base = settings.site_base_url if settings else None
        except Exception as e:
            app.logger.warning(f'unauthorized_handler: {e}')
            base = None
        if not base:
            base = ''
        return redirect(f'{base}/login')

    # Контекст-процессор: site_settings во всех шаблонах
    @app.context_processor
    def inject_site_settings():
        try:
            return {'site_settings': SiteSettings.get()}
        except Exception as e:
            app.logger.warning(f'inject_site_settings: {e}')
            return {'site_settings': None}

    # === W47: главная — INBOX ===

    @app.route('/')
    @login_required
    def index():
        """Главная: редирект на INBOX."""
        return redirect(url_for('inbox'))

    def _get_mailbox_info():
        """Собирает информацию о ящике текущего пользователя."""
        mailbox = Mailbox.query.filter_by(user_id=current_user.id).first()
        if not mailbox:
            return None, None

        quota_used = 0
        quota_error = None

        # Кэш квоты (60 сек) — GETQUOTAROOT через IMAP вместо doveadm
        cache_key_quota = f'mail_quota_{mailbox.email}'
        cached = cache.get(cache_key_quota)

        if cached is not None:
            quota_used = cached
        else:
            used, limit, err = imap_client.get_quota(mailbox.email)
            if err:
                quota_error = err
            else:
                quota_used = used
                cache.set(cache_key_quota, used, timeout=60)

        quota_total = mailbox.quota_bytes or 0
        percent = round(quota_used / quota_total * 100, 1) if quota_total > 0 else 0

        info = {
            'email': mailbox.email,
            'name': mailbox.name,
            'is_active': mailbox.is_active,
            'quota_total': quota_total,
            'quota_used': quota_used,
            'quota_free': max(0, quota_total - quota_used),
            'quota_percent': percent,
            'quota_error': quota_error,
            'last_login': mailbox.last_login,
        }
        return mailbox, info

    def _current_email():
        """Email ящика текущего пользователя (или None)."""
        mailbox = Mailbox.query.filter_by(user_id=current_user.id).first()
        return mailbox.email if mailbox else None

    # === W47 Этап 2: реальный IMAP ===

    def _render_inbox(folder_name='INBOX'):
        """Общий рендер трёхпанельного layout для папки."""
        email = _current_email()
        if not email:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('settings'))

        # === Папки (кэш 60 сек) ===
        cache_key_folders = f'mail_folders_{email}'
        folders = cache.get(cache_key_folders)
        folders_error = None
        if folders is None:
            folders, folders_error = imap_client.list_folders(email)
            if folders is not None:
                cache.set(cache_key_folders, folders, timeout=60)

        # === Список писем (кэш 30 сек) ===
        cache_key_msgs = f'mail_msgs_{email}_{folder_name}'
        messages = cache.get(cache_key_msgs)
        messages_error = None
        messages_total = 0
        if messages is None:
            messages, messages_total, messages_error = imap_client.list_messages(
                email, folder=folder_name, limit=50, offset=0,
            )
            if messages is not None:
                cache.set(cache_key_msgs, (messages, messages_total), timeout=30)
        else:
            # messages = (list, total) из кэша
            messages, messages_total = messages

        # Ошибки наверх
        if folders_error:
            flash(f'Папки: {folders_error}', 'warning')
        if messages_error:
            flash(f'Письма: {messages_error}', 'warning')

        # Человекочитаемое имя папки
        titles = {
            'INBOX': 'Входящие',
            'Sent': 'Отправленные',
            'Drafts': 'Черновики',
            'Junk': 'Спам',
            'Trash': 'Корзина',
        }
        folder_title = titles.get(folder_name, folder_name)

        return render_template(
            'index.html',
            folder_current=folder_name,
            folder_title=folder_title,
            folders=folders or [],
            messages=messages or [],
            messages_total=messages_total,
            message=None,
        )

    @app.route('/inbox')
    @login_required
    def inbox():
        """INBOX — трёхпанельный layout."""
        return _render_inbox('INBOX')

    @app.route('/folder/<path:name>')
    @login_required
    def folder(name):
        """Открывает папку."""
        return _render_inbox(name)

    @app.route('/message/<uid>')
    @login_required
    def message(uid):
        """Просмотр письма."""
        email = _current_email()
        if not email:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('settings'))

        folder_name = request.args.get('folder', 'INBOX')

        try:
            uid_int = int(uid)
        except ValueError:
            flash('Некорректный UID письма', 'danger')
            return redirect(url_for('inbox'))

        # === Само письмо (без кэша) ===
        msg, msg_error = imap_client.get_message(email, folder_name, uid_int)
        if msg_error:
            flash(msg_error, 'danger')

        # === Папки (кэш) ===
        cache_key_folders = f'mail_folders_{email}'
        folders = cache.get(cache_key_folders)
        if folders is None:
            folders, _ = imap_client.list_folders(email)
            if folders is not None:
                cache.set(cache_key_folders, folders, timeout=60)

        # === Список писем (кэш) ===
        cache_key_msgs = f'mail_msgs_{email}_{folder_name}'
        messages = cache.get(cache_key_msgs)
        messages_total = 0
        if messages is None:
            messages, messages_total, _ = imap_client.list_messages(
                email, folder=folder_name, limit=50, offset=0,
            )
            if messages is not None:
                cache.set(cache_key_msgs, (messages, messages_total), timeout=30)
        else:
            messages, messages_total = messages

        titles = {
            'INBOX': 'Входящие',
            'Sent': 'Отправленные',
            'Drafts': 'Черновики',
            'Junk': 'Спам',
            'Trash': 'Корзина',
        }
        folder_title = titles.get(folder_name, folder_name)

        return render_template(
            'index.html',
            folder_current=folder_name,
            folder_title=folder_title,
            folders=folders or [],
            messages=messages or [],
            messages_total=messages_total,
            message=msg,
        )

    @app.route('/api/message/<uid>')
    @login_required
    def api_message(uid):
        """AJAX: возвращает HTML-фрагмент письма (панель 3)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        folder_name = request.args.get('folder', 'INBOX')

        try:
            uid_int = int(uid)
        except ValueError:
            return jsonify({'ok': False, 'error': 'Некорректный UID'}), 400

        # === Письмо (с кэшем тел) ===
        msg, was_cached, msg_error = imap_client.get_message_cached(
            email, folder_name, uid_int
        )
        if msg_error:
            return jsonify({'ok': False, 'error': msg_error}), 500

        # === Инвалидация кэша заголовков ===
        # После открытия письмо помечается \Seen — заголовок в списке устарел.
        cache_key_msgs = f'mail_msgs_{email}_{folder_name}'
        cache.delete(cache_key_msgs)

        # === Рендер partial'а message_view ===
        html = render_template(
            'partials/message_view.html',
            message=msg,
        )

        return jsonify({
            'ok': True,
            'html': html,
            'uid': uid_int,
            'cached': was_cached,
        })

    @app.route('/api/attachment/<uid>/<int:index>')
    @login_required
    def api_attachment(uid, index):
        """Скачивание вложения из письма."""
        import base64
        from flask import Response

        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        folder_name = request.args.get('folder', 'INBOX')

        try:
            uid_int = int(uid)
        except ValueError:
            return jsonify({'ok': False, 'error': 'Некорректный UID'}), 400

        msg, was_cached, msg_error = imap_client.get_message_cached(
            email, folder_name, uid_int
        )
        if msg_error:
            return jsonify({'ok': False, 'error': msg_error}), 500

        attachments = msg.get('attachments', [])
        if index < 0 or index >= len(attachments):
            return jsonify({'ok': False, 'error': 'Вложение не найдено'}), 404

        att = attachments[index]
        data_b64 = att.get('data_b64')
        if not data_b64:
            return jsonify({'ok': False, 'error': 'Нет данных вложения'}), 500

        # Декодируем base64 → байты
        try:
            data = base64.b64decode(data_b64)
        except Exception as e:
            return jsonify({'ok': False, 'error': f'Ошибка декодирования: {e}'}), 500

        filename = att.get('filename', 'file')
        content_type = att.get('content_type', 'application/octet-stream')

        # Экранируем имя файла для заголовка
        from urllib.parse import quote
        filename_encoded = quote(filename)

        return Response(
            data,
            mimetype=content_type,
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{filename_encoded}",
                'Content-Length': str(len(data)),
            }
        )

    @app.route('/compose')
    @login_required
    def compose():
        """Форма отправки. Этап 1: заглушка."""
        return render_template(
            'index.html',
            folder_current='INBOX',
            folder_title='Входящие',
            messages=[],
            message=None,
        )

    @app.route('/settings')
    @login_required
    def settings():
        """Настройки почты. Этап 1: карточка ящика + IMAP."""
        mailbox, mailbox_info = _get_mailbox_info()
        return render_template(
            'settings.html',
            mailbox=mailbox,
            mailbox_info=mailbox_info,
        )

    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        """Смена пароля почтового ящика."""
        mailbox = Mailbox.query.filter_by(user_id=current_user.id).first()

        if not mailbox:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('index'))

        error = None

        if request.method == 'POST':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            # Проверки
            if not current_password or not new_password or not confirm_password:
                error = 'Заполните все поля'
            elif new_password != confirm_password:
                error = 'Пароли не совпадают'
            elif len(new_password) < 6:
                error = 'Пароль должен содержать минимум 6 символов'
            else:
                # Проверяем текущий пароль через Dovecot
                import subprocess
                try:
                    result = subprocess.run(
                        ['sudo', '/usr/bin/doveadm', 'auth', 'test', mailbox.email, current_password],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        error = 'Текущий пароль неверен'
                except Exception as e:
                    error = f'Ошибка проверки пароля: {e}'

                if not error:
                    # Генерируем новый хэш
                    ok, result = hash_password(new_password)
                    if not ok:
                        error = f'Ошибка создания пароля: {result}'
                    else:
                        mailbox.password_hash = result
                        db.session.commit()
                        flash('Пароль успешно изменён', 'success')
                        return redirect(url_for('index'))

        return render_template('change_password.html', mailbox=mailbox, error=error)

    @app.route('/health')
    def health():
        """Health-check для мониторинга."""
        return jsonify({
            'status': 'ok',
            'service': 'mail',
            'port': app.config['MAIL_PORT'],
        })

        # === ВНУТРЕННИЙ API (framework → mail) ===
    # Авторизация: X-Internal-Key (из INTERNAL_API_KEY)

    def _check_internal_key():
        """Проверяет X-Internal-Key. Возвращает True/False."""
        expected = app.config.get('INTERNAL_API_KEY') or os.getenv('INTERNAL_API_KEY')
        provided = request.headers.get('X-Internal-Key', '')
        if not expected:
            app.logger.error('INTERNAL_API_KEY не настроен')
            return False
        return provided == expected

    @app.route('/api/internal/hash-password', methods=['POST'])
    @csrf.exempt
    def api_internal_hash_password():
        """
        Принимает: {"password": "..."}
        Возвращает: {"ok": true, "hash": "{SHA512-CRYPT}$6$..."} или {"ok": false, "error": "..."}
        """
        if not _check_internal_key():
            return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

        data = request.get_json(silent=True) or {}
        password = data.get('password') or ''

        if not password:
            return jsonify({'ok': False, 'error': 'Пароль не задан'}), 400

        ok, result = hash_password(password)
        if not ok:
            return jsonify({'ok': False, 'error': result}), 500

        return jsonify({'ok': True, 'hash': result})

    @app.route('/api/internal/quota/<path:email>')
    @csrf.exempt
    def api_internal_quota(email):
        """
        Принимает: email в URL.
        Возвращает: {"ok": true, "used_bytes": N, "quota_bytes": M} или {"ok": false, "error": "..."}
        """
        if not _check_internal_key():
            return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

        ok, result = get_quota(email)
        if not ok:
            return jsonify({'ok': False, 'error': result}), 500

        return jsonify({
            'ok': True,
            'used_bytes': result['used_bytes'],
            'quota_bytes': result['quota_bytes'],
        })

    @app.route('/api/internal/reload/<service>', methods=['POST'])
    @csrf.exempt
    def api_internal_reload(service):
        """
        Перезагружает сервис (postfix, dovecot, rspamd).
        Возвращает: {"ok": true} или {"ok": false, "error": "..."}
        """
        if not _check_internal_key():
            return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

        ok, err = reload_service(service)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 400

        return jsonify({'ok': True})

    @app.route('/api/internal/archive-mailbox/<path:email>', methods=['POST'])
    @csrf.exempt
    def api_internal_archive_mailbox(email):
        """
        Архивирует Maildir ящика в .tar.gz.
        Возвращает: {"ok": true, "path": "..."} или {"ok": true, "path": null} (если нечего)
                    или {"ok": false, "error": "..."}
        """
        if not _check_internal_key():
            return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

        ok, result = archive_mailbox(email)
        if not ok:
            return jsonify({'ok': False, 'error': result}), 500

        return jsonify({'ok': True, 'path': result})

    return app


app = create_app()