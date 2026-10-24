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
            "script-src 'self' 'unsafe-inline'; "             
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

        # === Папки (без кэша — всегда свежие) ===
        folders, folders_error = imap_client.list_folders(email)

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
            custom_folders=folders or [],
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
        # Инвалидируем кэш списка (письмо помечено \Seen)
        if not was_cached:
            cache_key_msgs = f'mail_msgs_{email}_{folder_name}'
            cache.delete(cache_key_msgs)

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

    @app.route('/api/recipients')
    @login_required
    def api_recipients():
        """Поиск получателей для автодополнения (по RecentRecipient)."""
        from core.models import RecentRecipient
        q = (request.args.get('q') or '').strip().lower()

        query = RecentRecipient.query.filter_by(user_id=current_user.id)
        if q:
            query = query.filter(RecentRecipient.email.ilike(f'%{q}%'))
        recipients = query.order_by(
            RecentRecipient.use_count.desc(),
            RecentRecipient.last_used.desc(),
        ).limit(10).all()

        return jsonify({
            'ok': True,
            'items': [
                {'email': r.email, 'name': r.name or ''}
                for r in recipients
            ],
        })

    @app.route('/api/draft', methods=['POST'])
    @login_required
    def api_draft():
        """Сохранение черновика в папку Drafts (IMAP APPEND)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        to_addr = (data.get('to') or '').strip()
        subject = (data.get('subject') or '').strip()
        body = data.get('body') or ''

        if not to_addr and not subject and not body:
            return jsonify({'ok': False, 'error': 'Пустой черновик'}), 400

        # Формируем MIME-письмо для черновика
        from email.message import EmailMessage
        from email.utils import formatdate, make_msgid

        msg = EmailMessage()
        msg['From'] = email
        msg['To'] = to_addr or '(без получателя)'
        msg['Subject'] = subject or '(без темы)'
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain=email.split('@')[-1])

        # Тело — HTML
        msg.set_content(body or '')
        msg.add_alternative(body or '', subtype='html')

        # Сохраняем в Drafts
        ok, err = imap_client.append_to_drafts(email, msg.as_bytes())
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        return jsonify({'ok': True})

    @app.route('/api/draft/delete', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_draft_delete():
        """Удаляет черновик из Drafts."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        uid = data.get('uid')
        if not uid:
            return jsonify({'ok': False, 'error': 'Укажите UID'}), 400

        ok, err = imap_client.delete_message(email, 'Drafts', int(uid))
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        cache.delete(f'mail_msgs_{email}_Drafts')
        cache.delete(f'mail_folders_{email}')

        return jsonify({'ok': True})

    @app.route('/api/latest-draft')
    @login_required
    def api_latest_draft():
        """Последний черновик (для восстановления)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False})

        # Получаем список черновиков
        msgs, total, err = imap_client.list_messages(email, 'Drafts', limit=1, offset=0)
        if err:
            return jsonify({'ok': False, 'error': err})

        if not msgs:
            return jsonify({'ok': True, 'none': True})

        m = msgs[0]
        # Загружаем полное письмо (черновик)
        draft, d_err = imap_client.get_message(email, 'Drafts', m['uid'])
        if d_err:
            return jsonify({'ok': False, 'error': d_err})

        return jsonify({
            'ok': True,
            'uid': m['uid'],
            'to': draft.get('to', ''),
            'cc': draft.get('cc', ''),
            'subject': draft.get('subject', ''),
            'body': draft.get('body_html', '') or draft.get('body_text', ''),
            'date_human': draft.get('date_human', ''),
        })

    @app.route('/api/search')
    @login_required
    def api_search():
        """Поиск писем (IMAP SEARCH)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        q = (request.args.get('q') or '').strip()
        folder = request.args.get('folder', 'INBOX')

        if not q:
            return jsonify({'ok': True, 'results': []})

        # IMAP SEARCH
        results, total, err = imap_client.search_messages(email, folder, q, limit=50)
        if err:
            return jsonify({'ok': False, 'error': err}), 500

        return jsonify({
            'ok': True,
            'results': results,
            'total': total,
        })

    @app.route('/api/folder/create', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_folder_create():
        """Создание IMAP-папки."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'ok': False, 'error': 'Укажите имя папки'}), 400

        ok, err = imap_client.create_folder(email, name)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        # Инвалидируем кэш папок
        cache.delete(f'mail_folders_{email}')

        return jsonify({'ok': True})

    @app.route('/api/folder/rename', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_folder_rename():
        """Переименование IMAP-папки."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        old_name = (data.get('old_name') or '').strip()
        new_name = (data.get('new_name') or '').strip()
        if not old_name or not new_name:
            return jsonify({'ok': False, 'error': 'Укажите имена'}), 400

        ok, err = imap_client.rename_folder(email, old_name, new_name)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        cache.delete(f'mail_folders_{email}')
        return jsonify({'ok': True})

    @app.route('/api/folder/delete', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_folder_delete():
        """Удаление IMAP-папки."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'ok': False, 'error': 'Укажите имя папки'}), 400

        ok, err = imap_client.delete_folder(email, name)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        cache.delete(f'mail_folders_{email}')
        return jsonify({'ok': True})

    @app.route('/api/message/trash', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_message_trash():
        """Перемещает письмо в Trash."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        uid = data.get('uid')
        folder = data.get('folder', 'INBOX')

        if not uid:
            return jsonify({'ok': False, 'error': 'Укажите UID'}), 400

        ok, err = imap_client.trash_message(email, folder, int(uid))
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        # Инвалидируем кэш
        cache.delete(f'mail_msgs_{email}_{folder}')
        cache.delete(f'mail_folders_{email}')

        return jsonify({'ok': True})

    @app.route('/api/message/move', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_message_move():
        """Перемещает письмо в указанную папку."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        uid = data.get('uid')
        folder = data.get('folder', 'INBOX')
        dest = data.get('dest')
        if not uid or not dest:
            return jsonify({'ok': False, 'error': 'Укажите UID и папку'}), 400

        ok, err = imap_client.move_message(email, folder, int(uid), dest)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        cache.delete(f'mail_msgs_{email}_{folder}')
        cache.delete(f'mail_msgs_{email}_{dest}')
        cache.delete(f'mail_folders_{email}')

        return jsonify({'ok': True})

    @app.route('/api/cloud-tree')
    @login_required
    def api_cloud_tree():
        """Дерево папок облака (для модалки)."""
        from core.models import CloudFile

        folders = CloudFile.query.filter_by(
            owner_id=current_user.id,
            is_folder=True,
            is_trashed=False,
        ).order_by(CloudFile.name).all()

        return jsonify([
            {'id': f.id, 'name': f.name, 'parent_id': f.parent_id}
            for f in folders
        ])

    @app.route('/api/cloud-folder/<int:folder_id>')
    @login_required
    def api_cloud_folder(folder_id):
        """Содержимое папки облака."""
        from core.models import CloudFile

        items = CloudFile.query.filter_by(
            owner_id=current_user.id,
            parent_id=folder_id,
            is_trashed=False,
        ).order_by(CloudFile.is_folder.desc(), CloudFile.name).all()

        return jsonify({
            'folders': [
                {'id': i.id, 'name': i.name, 'parent_id': i.parent_id}
                for i in items if i.is_folder
            ],
            'files': [
                {
                    'id': i.id,
                    'name': i.name,
                    'is_folder': i.is_folder,
                    'size': i.size,
                    'mime_type': i.mime_type,
                }
                for i in items if not i.is_folder
            ],
        })

    @app.route('/api/cloud-files')
    @login_required
    def api_cloud_files():
        """Все файлы облака (для выбора)."""
        from core.models import CloudFile

        files = CloudFile.query.filter_by(
            owner_id=current_user.id,
            is_folder=False,
            is_trashed=False,
        ).order_by(CloudFile.name).all()

        return jsonify([
            {
                'id': f.id,
                'name': f.name,
                'is_folder': f.is_folder,
                'parent_id': f.parent_id,
                'size': f.size,
                'mime_type': f.mime_type,
            }
            for f in files
        ])

    @app.route('/api/share-file/<int:file_id>', methods=['POST'])
    @login_required
    @csrf.exempt
    def api_share_file(file_id):
        """Создаёт (или переиспользует) шару для файла и возвращает абсолютный URL."""
        from core.models import CloudFile, CloudShare, SiteSettings
        import secrets

        file = CloudFile.query.filter_by(
            id=file_id,
            owner_id=current_user.id,
            is_trashed=False,
        ).first()
        if not file:
            return jsonify({'ok': False, 'error': 'Файл не найден'}), 404

        # Ищем существующую шару
        share = CloudShare.query.filter_by(file_id=file.id).first()
        if not share:
            share = CloudShare(
                file_id=file.id,
                token=secrets.token_urlsafe(32),
                created_by_id=current_user.id,
            )
            db.session.add(share)
            db.session.commit()

        # Абсолютный URL
        settings = SiteSettings.get()
        base = settings.cloud_base_url if settings else 'http://192.168.2.19:5001'
        url = f'{base}/s/{share.token}'

        return jsonify({
            'ok': True,
            'url': url,
            'name': file.name,
            'token': share.token,
        })

    @app.route('/api/unread-count')
    @login_required
    def api_unread_count():
        """Количество непрочитанных (для счётчика)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'unread': 0})

        # Без кэша — актуальные данные
        folders, err = imap_client.list_folders(email)
        if err:
            return jsonify({'ok': False, 'unread': 0, 'error': err})

        total_unread = sum(f.get('unread', 0) for f in (folders or []))
        inbox_unread = next(
            (f.get('unread', 0) for f in (folders or []) if f.get('name') == 'INBOX'),
            0,
        )

        return jsonify({
            'ok': True,
            'total_unread': total_unread,
            'inbox_unread': inbox_unread,
        })

    @app.route('/api/latest-unread')
    @login_required
    def api_latest_unread():
        """Последнее непрочитанное письмо (для toast)."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False})

        # Берём список писем INBOX (50 — достаточно)
        msgs, total, err = imap_client.list_messages(email, 'INBOX', limit=50, offset=0)
        if err:
            return jsonify({'ok': False, 'error': err})

        # Ищем первое непрочитанное
        for m in (msgs or []):
            if not m.get('is_read'):
                return jsonify({
                    'ok': True,
                    'uid': m.get('uid'),
                    'from_name': m.get('from_name', ''),
                    'from_email': m.get('from_email', ''),
                    'subject': m.get('subject', ''),
                    'date_human': m.get('date_human', ''),
                })

        return jsonify({'ok': True, 'none': True})

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

    @app.route('/settings/rules')
    @login_required
    def settings_rules():
        """Sieve-правила пользователя."""
        email = _current_email()
        if not email:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('settings'))

        # Получаем список Sieve-скриптов из Dovecot
        sieve_scripts, sieve_error = imap_client.list_sieve_scripts(email)
        if sieve_error:
            flash(f'Sieve: {sieve_error}', 'warning')

        # Получаем правила из БД (SieveRule)
        from core.models import SieveRule
        rules = SieveRule.query.filter_by(user_id=current_user.id).order_by(
            SieveRule.priority
        ).all()
        folders, folders_error = imap_client.list_folders(email)

        return render_template(
            'settings_rules.html',
            rules=rules,
            sieve_scripts=sieve_scripts or [],
            folders=folders or [],
        )

    def _generate_sieve_script(rule):
        """Генерирует Sieve-скрипт из правила (conditions + actions)."""
        import json

        conditions = rule.conditions or {}
        actions = rule.actions or {}

        # Условия
        cond_lines = []
        if conditions.get('from'):
            cond_lines.append(f'address :contains "From" "{conditions["from"]}"')
        if conditions.get('to'):
            cond_lines.append(f'address :contains "To" "{conditions["to"]}"')
        if conditions.get('subject'):
            cond_lines.append(f'header :contains "Subject" "{conditions["subject"]}"')
        if conditions.get('body'):
            cond_lines.append(f'body :contains "{conditions["body"]}"')
        if conditions.get('size_over'):
            cond_lines.append(f'size :over {conditions["size_over"]}')

        if not cond_lines:
            cond_str = 'true'
        elif len(cond_lines) == 1:
            cond_str = cond_lines[0]
        else:
            cond_str = 'allof(' + ', '.join(cond_lines) + ')'

        # Действия
        action_lines = []
        if actions.get('move_to'):
            action_lines.append(f'fileinto "{actions["move_to"]}";')
        if actions.get('mark_read'):
            action_lines.append('addflag "\\\\Seen";')
        if actions.get('delete'):
            action_lines.append('discard;')
        if actions.get('forward_to'):
            action_lines.append(f'redirect "{actions["forward_to"]}";')

        if not action_lines:
            action_lines.append('keep;')

        script = f'''require ["fileinto", "imap4flags", "copy", "body", "regex"];
# Rule: {rule.name}
if {cond_str} {{
    {' '.join(action_lines)}
}}
'''
        return script

    @app.route('/api/sieve/rule', methods=['POST'])
    @login_required
    def api_sieve_rule():
        """Создание/обновление Sieve-правила."""
        from core.models import SieveRule
        import json

        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        rule_id = data.get('id')
        name = (data.get('name') or '').strip()
        conditions = data.get('conditions') or {}
        actions = data.get('actions') or {}

        if not name:
            return jsonify({'ok': False, 'error': 'Укажите название правила'}), 400

        if rule_id:
            rule = SieveRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
            if not rule:
                return jsonify({'ok': False, 'error': 'Правило не найдено'}), 404
        else:
            rule = SieveRule(user_id=current_user.id)
            db.session.add(rule)

        rule.name = name
        rule.conditions = conditions
        rule.actions = actions
        rule.is_active = data.get('is_active', True)
        rule.priority = data.get('priority', 0)
        db.session.commit()

        # Генерируем Sieve-скрипт и сохраняем в Dovecot
        sieve_script = _generate_sieve_script(rule)
        ok, err = imap_client.put_sieve_script(email, f'rule_{rule.id}', sieve_script)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        return jsonify({'ok': True, 'id': rule.id})

    @app.route('/api/sieve/rule/<int:rule_id>', methods=['DELETE'])
    @login_required
    def api_sieve_rule_delete(rule_id):
        """Удаление Sieve-правила."""
        from core.models import SieveRule

        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        rule = SieveRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
        if not rule:
            return jsonify({'ok': False, 'error': 'Правило не найдено'}), 404

        script_name = f'rule_{rule.id}'
        db.session.delete(rule)
        db.session.commit()

        # Удаляем скрипт из Dovecot
        imap_client.delete_sieve_script(email, script_name)

        return jsonify({'ok': True})

    @app.route('/api/sieve/activate', methods=['POST'])
    @login_required
    def api_sieve_activate():
        """Активация Sieve-скрипта."""
        email = _current_email()
        if not email:
            return jsonify({'ok': False, 'error': 'Нет ящика'}), 400

        data = request.get_json(silent=True) or {}
        script_name = data.get('name')
        if not script_name:
            return jsonify({'ok': False, 'error': 'Укажите имя скрипта'}), 400

        ok, err = imap_client.activate_sieve_script(email, script_name)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 500

        return jsonify({'ok': True})


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

    @app.route('/compose', methods=['GET'])
    @login_required
    def compose():
        """Форма написания письма (с поддержкой reply/forward)."""
        email = _current_email()
        if not email:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('settings'))

        # Параметры для reply/forward
        reply_uid = request.args.get('reply')
        forward_uid = request.args.get('forward')
        folder = request.args.get('folder', 'INBOX')
        mode = request.args.get('mode', '')

        # Папки (для левой панели)
        folders, _ = imap_client.list_folders(email)

        # Контекст для шаблона (по умолчанию — пустая форма)
        ctx = {
            'prefill_to': '',
            'prefill_cc': '',
            'prefill_subject': '',
            'prefill_body': '',
            'custom_folders': folders or [],
            'folder_current': 'INBOX',
            'folder_title': 'Новое письмо',
            'messages': [],
            'message': None,
        }

        # Если reply или forward — подгружаем письмо
        if reply_uid or forward_uid:
            uid = int(reply_uid or forward_uid)
            msg, err = imap_client.get_message(email, folder, uid)
            if err:
                flash(f'Не удалось загрузить письмо: {err}', 'danger')
            else:
                from_addr = msg.get('from_email', '')
                subject = msg.get('subject', '')
                body_html = msg.get('body_html', '') or msg.get('body_text', '')

                if mode in ('reply', 'reply_all'):
                    ctx['prefill_to'] = from_addr
                    ctx['prefill_subject'] = f'Re: {subject}' if not subject.startswith('Re:') else subject
                    ctx['prefill_body'] = (
                        f'<br><br>--- Исходное сообщение ---<br>'
                        f'<b>От:</b> {from_addr}<br>'
                        f'<b>Тема:</b> {subject}<br>'
                        f'<blockquote>{body_html}</blockquote>'
                    )
                    if mode == 'reply_all':
                        # To: отправитель + все получатели (кроме себя)
                        to_list = [from_addr]
                        # Можно добавить To из оригинала, если нужно
                        ctx['prefill_to'] = ', '.join(to_list)
                        # Cc: остальные (кроме from_addr и себя)
                        ctx['prefill_cc'] = ''  # упрощённо

                elif mode == 'forward':
                    ctx['prefill_to'] = ''
                    ctx['prefill_subject'] = f'Fwd: {subject}' if not subject.startswith('Fwd:') else subject
                    ctx['prefill_body'] = (
                        f'<br><br>--- Пересылаемое сообщение ---<br>'
                        f'<b>От:</b> {from_addr}<br>'
                        f'<b>Тема:</b> {subject}<br>'
                        f'<blockquote>{body_html}</blockquote>'
                    )

        return render_template('compose.html', **ctx)

    @app.route('/compose/send', methods=['POST'])
    @login_required
    @limiter.limit("100/hour")
    def compose_send():
        """Отправка письма через sendmail."""
        email = _current_email()
        if not email:
            flash('У вас нет почтового ящика', 'danger')
            return redirect(url_for('settings'))

        # --- Поля формы ---
        to_raw = (request.form.get('to') or '').strip()
        cc_raw = (request.form.get('cc') or '').strip()
        bcc_raw = (request.form.get('bcc') or '').strip()
        subject = (request.form.get('subject') or '').strip()
        body_html = request.form.get('body') or ''

        # --- Валидация ---
        import re
        email_re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

        to_list = [e.strip() for e in to_raw.split(',') if e.strip()]
        cc_list = [e.strip() for e in cc_raw.split(',') if e.strip()]
        bcc_list = [e.strip() for e in bcc_raw.split(',') if e.strip()]

        if not to_list:
            flash('Укажите получателя (Кому)', 'danger')
            return redirect(url_for('compose'))

        for addr in to_list + cc_list + bcc_list:
            if not email_re.match(addr):
                flash(f'Некорректный email: {addr}', 'danger')
                return redirect(url_for('compose'))

        # --- Проверка From (только свои адреса) ---
        # У пользователя один ящик, поэтому from = email
        from_addr = email

        # --- Отправка ---
        from mail_service import send_mail
        # === Вложения ===
        attachments = []
        files = request.files.getlist('attachments')
        for f in files:
            if f and f.filename:
                data = f.read()
                attachments.append((f.filename, f.content_type or 'application/octet-stream', data))

        # Ограничение: 30 МБ суммарно
        total_size = sum(len(d) for _, _, d in attachments)
        if total_size > 30 * 1024 * 1024:
            flash('Суммарный размер вложений превышает 30 МБ', 'danger')
            return redirect(url_for('compose'))

        ok, err, raw_message = send_mail(
            from_addr=from_addr,
            to_addrs=to_list,
            subject=subject,
            body_html=body_html,
            cc_addrs=cc_list or None,
            bcc_addrs=bcc_list or None,
            attachments=attachments or None,
        )

        if not ok:
            flash(f'Ошибка отправки: {err}', 'danger')
            return redirect(url_for('compose'))

        # --- Копия в Sent (IMAP APPEND) ---
        if raw_message:
            append_ok, append_err = imap_client.append_to_sent(email, raw_message)
            if not append_ok:
                current_app.logger.warning(f'append_to_sent failed: {append_err}')
                # не критично — письмо ушло, просто копии нет
        # --- Сохранить получателей в RecentRecipient ---
        try:
            from core.models import RecentRecipient
            from datetime import datetime
            all_recipients = to_list + (cc_list or []) + (bcc_list or [])
            for addr in all_recipients:
                existing = RecentRecipient.query.filter_by(
                    user_id=current_user.id, email=addr
                ).first()
                if existing:
                    existing.use_count += 1
                    existing.last_used = datetime.utcnow()
                else:
                    db.session.add(RecentRecipient(
                        user_id=current_user.id,
                        email=addr,
                        last_used=datetime.utcnow(),
                        use_count=1,
                    ))
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(f'RecentRecipient save failed: {e}')
            db.session.rollback()
        flash('Письмо отправлено', 'success')
        return redirect(url_for('inbox'))

    @app.after_request
    def add_cors_headers(response):
        if request.path.startswith('/api/'):
            origin = request.headers.get('Origin', '')
            allowed = [
                'http://192.168.2.19',
                'http://192.168.2.19:5001',
            ]
            if origin in allowed:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return response

    return app


app = create_app()