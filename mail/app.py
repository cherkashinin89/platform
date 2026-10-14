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
from core.extensions import db, login_manager, csrf, migrate
from core.models import User, MailDomain, Mailbox, SiteSettings
from mail_service import hash_password, get_quota, reload_service, archive_mailbox


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

    # === МАРШРУТЫ ===

    @app.route('/')
    @login_required
    def index():
        """Главная страница mail-сервиса: информация о ящике пользователя."""
        # Находим ящик текущего пользователя (у нас 1:1)
        mailbox = Mailbox.query.filter_by(user_id=current_user.id).first()

        mailbox_info = None
        if mailbox:
            quota_used = 0
            quota_error = None
            ok, q = get_quota(mailbox.email)
            if ok:
                quota_used = q.get('used_bytes', 0)
            else:
                quota_error = q

            quota_total = mailbox.quota_bytes or 0
            percent = round(quota_used / quota_total * 100, 1) if quota_total > 0 else 0

            mailbox_info = {
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

        return render_template('index.html', mailbox=mailbox, mailbox_info=mailbox_info)

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