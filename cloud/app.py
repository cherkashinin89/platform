# app.py - Облачное хранилище MyCloud
import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file
from jinja2 import ChoiceLoader, FileSystemLoader
from flask_login import (
    login_required, current_user
)

from config import Config
from cloud_service import (
    list_folder, get_folder, get_item, get_file,
    build_breadcrumbs, get_quota_info, get_trashed_bytes,
    has_enough_space, format_bytes,
    create_folder, validate_name, name_exists,
    save_uploaded_file, rename_item, trash_item,
    list_trash, count_trash, restore_item,
    delete_item_permanently,
    create_share, get_share_by_token, list_shares, revoke_share,
    increment_share_download, get_all_folders, icon_for_file,
    icon_for_folder, move_item
)
from core.extensions import db, login_manager, csrf, migrate
from core.models import User, CloudFile, CloudShare, SiteSettings

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ШАРИНГА ===

def _is_descendant_of(item, root):
    """
    Проверяет, что item — потомок root (на любом уровне).
    root сам item'ом НЕ считается (нужен настоящий потомок).
    """
    current = item
    guard = 0
    while current and guard < 100:
        if current.parent_id == root.id:
            return True
        current = CloudFile.query.get(current.parent_id) if current.parent_id else None
        guard += 1
    return False


def _public_breadcrumbs(root, current, token):
    """
    Строит крошки для публичного просмотра:
    root (сама папка-шаринг) → ... → current
    Каждая ссылка — с ?folder=<id>
    """
    crumbs = [{
        'id': root.id,
        'name': root.name,
        'url': f'/s/{token}',
    }]

    if current.id == root.id:
        return crumbs

    # Собираем путь от current вверх до root
    chain = []
    node = current
    guard = 0

    while node and node.id != root.id and guard < 100:
        chain.append({
            'id': node.id,
            'name': node.name,
            'url': f'/s/{token}?folder={node.id}',
        })
        node = CloudFile.query.get(node.parent_id) if node.parent_id else None
        guard += 1

    chain.reverse()
    crumbs.extend(chain)
    return crumbs

def create_app(config_class=Config):
    """Создаёт и настраивает экземпляр Flask для облака"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # === Подключаем шаблоны core (общие) + локальные ===
    # Приоритет: cloud/templates/ → core/templates/
    core_templates = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'core', 'templates'
    )
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(core_templates),
    ])

    # === Jinja-фильтры ===
    # format_bytes доступен во всех шаблонах как | format_bytes
    app.jinja_env.filters['format_bytes'] = format_bytes
    app.jinja_env.filters['icon_for_file'] = icon_for_file
    app.jinja_env.filters['icon_for_folder'] = icon_for_folder

    # === Инициализация расширений ===
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # === Загрузчик пользователя для Flask-Login ===
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # === Контекст-процессор: делает site_settings доступными во всех шаблонах ===
    @app.context_processor
    def inject_site_settings():
        """
        Передаёт настройки сайта во все шаблоны.
        Если таблицы ещё нет или данных нет — возвращает None.
        """
        try:
            return {'site_settings': SiteSettings.get()}
        except Exception as e:
            app.logger.warning(f'inject_site_settings: {e}')
            return {'site_settings': None}

    # === Обработчик «не авторизован» ===
    # Вместо собственной страницы логина — редирект на myframework.
    @login_manager.unauthorized_handler
    def unauthorized():
        # Отправляем на основную страницу входа основного приложения.
        # URL берём из SiteSettings (общая БД), чтобы не хардкодить IP/домен.
        try:
            settings = SiteSettings.get()
            base = settings.site_base_url if settings else None
        except Exception as e:
            app.logger.warning(f'unauthorized_handler: {e}')
            base = None
        if not base:
            base = ''
        return redirect(f'{base}/login')

    # === КОРНЕВОЙ МАРШРУТ (проверка каркаса) ===
    @app.route('/')
    @app.route('/folder/<int:folder_id>')
    @login_required
    def index(folder_id=None):
        """
        Главная страница облака: список файлов в корне или в папке.
        """
        # Проверяем, что если folder_id задан — папка наша и существует
        if folder_id is not None:
            folder = get_folder(current_user.id, folder_id)
            if not folder:
                flash('Папка не найдена', 'warning')
                return redirect(url_for('index'))
        else:
            folder = None

        # Получаем содержимое текущей папки
        items = list_folder(current_user.id, parent_id=folder_id)

        # Хлебные крошки
        breadcrumbs = build_breadcrumbs(current_user.id, folder_id)

        # Информация о квоте
        quota = get_quota_info(current_user)

        return render_template(
            'index.html',
            folder=folder,
            items=items,
            breadcrumbs=breadcrumbs,
            quota=quota,
        )

       # === API: СОЗДАНИЕ ПАПКИ ===

    @app.route('/api/folder', methods=['POST'])
    @login_required
    def api_create_folder():
        """
        Создаёт папку.
        Принимает JSON: {"name": "Документы", "parent_id": null}
        Возвращает JSON: {"ok": true, "folder": {...}} или {"ok": false, "error": "..."}
        """
        data = request.get_json(silent=True) or {}

        name = (data.get('name') or '').strip()
        parent_id = data.get('parent_id')

        # Приводим parent_id к int, если он задан
        if parent_id is not None:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return jsonify({'ok': False, 'error': 'Неверный parent_id'}), 400

        # Создаём
        ok, result = create_folder(current_user.id, name, parent_id)

        if not ok:
            return jsonify({'ok': False, 'error': result}), 400

        # Успех
        folder = result
        return jsonify({
            'ok': True,
            'folder': {
                'id': folder.id,
                'name': folder.name,
                'parent_id': folder.parent_id,
                'is_folder': True,
                'created_at': folder.created_at.isoformat() if folder.created_at else None,
            },
        })

        # === API: ЗАГРУЗКА ФАЙЛОВ ===

    @app.route('/api/upload', methods=['POST'])
    @login_required
    def api_upload():
        """
        Загружает один или несколько файлов.
        Принимает multipart/form-data:
          - files[] — файлы (поле 'files')
          - parent_id — ID родительской папки или пусто (корень)

        Возвращает JSON:
          {
            "ok": true,
            "uploaded": [{"id": 5, "name": "файл.txt", "size": 1234}, ...],
            "errors": [{"name": "файл2.txt", "error": "..."}]
          }
        """
        # Получаем список файлов
        files = request.files.getlist('files')
        files = [f for f in files if f and f.filename]

        if not files:
            return jsonify({'ok': False, 'error': 'Файлы не выбраны'}), 400

        # parent_id
        parent_id = request.form.get('parent_id')
        if parent_id in (None, '', 'null'):
            parent_id = None
        else:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return jsonify({'ok': False, 'error': 'Неверный parent_id'}), 400

        uploaded = []
        errors = []

        for f in files:
            ok, result = save_uploaded_file(current_user.id, f, parent_id)

            if ok:
                uploaded.append({
                    'id': result.id,
                    'name': result.name,
                    'size': result.size,
                    'size_human': format_bytes(result.size),
                    'mime': result.mime_type,
                })
            else:
                errors.append({
                    'name': f.filename,
                    'error': result,   # текст ошибки
                })

        return jsonify({
            'ok': True,
            'uploaded': uploaded,
            'errors': errors,
        })

        # === API: ДЕРЕВО ПАПОК ===

    @app.route('/api/tree')
    @login_required
    def api_tree():
        """
        Возвращает плоский список всех папок пользователя (не в корзине).
        Формат: {"ok": true, "folders": [{"id": 1, "name": "...", "parent_id": null}, ...]}
        """
        folders = get_all_folders(current_user.id)
        return jsonify({
            'ok': True,
            'folders': folders,
        })

        # === API: СКАЧИВАНИЕ ===

    @app.route('/api/download/<int:file_id>')
    @login_required
    def api_download(file_id):
        """
        Отдаёт файл пользователю.

        Query-параметры:
          - disposition=attachment (по умолчанию) — скачать
          - disposition=inline                    — открыть в браузере

        Безопасность: проверяем, что файл принадлежит current_user.
        """
        import os
        from flask import current_app, abort

        # 1. Находим файл в БД, проверяем владельца
        record = get_file(current_user.id, file_id, allow_trashed=False)
        if not record:
            abort(404, description='Файл не найден')

        # 2. Собираем путь
        user_dir = os.path.join(
            current_app.config['CLOUD_DATA_DIR'],
            str(current_user.id),
        )
        file_path = os.path.join(user_dir, record.stored_name)

        # 3. Дополнительная проверка на path traversal
        abs_file = os.path.abspath(file_path)
        abs_dir = os.path.abspath(user_dir)
        if not abs_file.startswith(abs_dir + os.sep):
            abort(403, description='Недопустимый путь')

        # 4. Проверяем, что файл существует
        if not os.path.isfile(file_path):
            abort(404, description='Файл отсутствует на диске')

        # 5. disposition
        disposition = request.args.get('disposition', 'attachment')
        if disposition not in ('inline', 'attachment'):
            disposition = 'attachment'

        # 6. Отдаём
        return send_file(
            file_path,
            mimetype=record.mime_type or 'application/octet-stream',
            as_attachment=(disposition == 'attachment'),
            download_name=record.name,
            conditional=True,     # поддержка Range-запросов (докачка, видео)
        )    

        # === API: ПЕРЕИМЕНОВАНИЕ ===

    @app.route('/api/rename/<int:item_id>', methods=['POST'])
    @login_required
    def api_rename(item_id):
        """
        Переименовывает файл или папку.
        Принимает JSON: {"name": "новое_имя"}
        Возвращает JSON: {"ok": true, "item": {...}} или {"ok": false, "error": "..."}
        """
        data = request.get_json(silent=True) or {}
        new_name = (data.get('name') or '').strip()

        if not new_name:
            return jsonify({'ok': False, 'error': 'Имя не задано'}), 400

        ok, result = rename_item(current_user.id, item_id, new_name)

        if not ok:
            return jsonify({'ok': False, 'error': result}), 400

        item = result
        return jsonify({
            'ok': True,
            'item': {
                'id': item.id,
                'name': item.name,
                'is_folder': item.is_folder,
                'size': item.size,
                'updated_at': item.updated_at.isoformat() if item.updated_at else None,
            },
        })

        # === API: УДАЛЕНИЕ В КОРЗИНУ ===

    @app.route('/api/trash/<int:item_id>', methods=['POST'])
    @login_required
    def api_trash(item_id):
        """
        Мягкое удаление: помещает элемент и всех потомков в корзину.
        Возвращает JSON: {"ok": true, "count": N} или {"ok": false, "error": "..."}
        """
        ok, result = trash_item(current_user.id, item_id)

        if not ok:
            return jsonify({'ok': False, 'error': result}), 400

        return jsonify({
            'ok': True,
            'count': result['count'],
            'name': result['item'].name,
        })

        # === API: ВОССТАНОВЛЕНИЕ ИЗ КОРЗИНЫ ===

    @app.route('/api/restore/<int:item_id>', methods=['POST'])
    @login_required
    def api_restore(item_id):
        """
        Восстанавливает элемент из корзины.
        Возвращает JSON: {"ok": true, "count": N, "name": "..."} или {"ok": false, "error": "..."}
        """
        ok, result = restore_item(current_user.id, item_id)

        if not ok:
            return jsonify({'ok': False, 'error': result}), 400

        return jsonify({
            'ok': True,
            'count': result['count'],
            'name': result['item'].name,
            'restored_parents': result.get('restored_parents', 0),
        })

        # === API: ПЕРЕМЕЩЕНИЕ ===

    @app.route('/api/move', methods=['POST'])
    @login_required
    def api_move():
        """
        Перемещает элемент(ы) в новую папку.

        JSON: {"item_ids": [1, 2, 3], "new_parent_id": 5 | null}

        Возвращает: {"ok": true, "moved": N, "errors": [...]}
        """
        data = request.get_json(silent=True) or {}
        item_ids = data.get('item_ids') or []
        new_parent_id = data.get('new_parent_id')

        # Нормализация
        if not isinstance(item_ids, list) or not item_ids:
            return jsonify({'ok': False, 'error': 'Не указаны элементы'}), 400

        try:
            item_ids = [int(x) for x in item_ids]
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Неверные ID'}), 400

        if new_parent_id in (None, '', 'null'):
            new_parent_id = None
        else:
            try:
                new_parent_id = int(new_parent_id)
            except (TypeError, ValueError):
                return jsonify({'ok': False, 'error': 'Неверный new_parent_id'}), 400

        moved = 0
        errors = []

        for item_id in item_ids:
            ok, result = move_item(current_user.id, item_id, new_parent_id)
            if ok:
                moved += 1
            else:
                errors.append({'id': item_id, 'error': result})

        return jsonify({
            'ok': True,
            'moved': moved,
            'errors': errors,
        })
    
    # === ВРЕМЕННЫЙ МАРШРУТ ДЛЯ ПРОВЕРКИ АВТОРИЗАЦИИ ===
    @app.route('/whoami')
    @login_required
    def whoami():
        """Показывает данные текущего пользователя — для отладки."""
        return f"""
        <h2>Облако — проверка авторизации</h2>
        <ul>
            <li>ID: {current_user.id}</li>
            <li>Username: {current_user.username}</li>
            <li>Email: {current_user.email}</li>
            <li>Role: {current_user.role}</li>
            <li>is_admin: {current_user.is_admin}</li>
            <li>is_user: {current_user.is_user}</li>
        </ul>
        <p><a href="/">На главную</a></p>
        """

        # === КОРЗИНА ===

    @app.route('/trash')
    @login_required
    def trash():
        """Страница корзины: список удалённых элементов."""
        items = list_trash(current_user.id)
        total_count = count_trash(current_user.id)
        quota = get_quota_info(current_user)

        return render_template(
            'trash.html',
            items=items,
            total_count=total_count,
            quota=quota,
        )

        # === МОИ ССЫЛКИ ===

    @app.route('/shares')
    @login_required
    def shares():
        """Страница со списком всех публичных ссылок пользователя."""
        shares_list = list_shares(current_user.id)
        quota = get_quota_info(current_user)

        return render_template(
            'shares.html',
            shares=shares_list,
            quota=quota,
        )


        # === ПУБЛИЧНЫЙ ДОСТУП ПО ССЫЛКЕ (без авторизации) ===

    @app.route('/s/<token>')
    def public_share(token):
        """
        Публичная страница по ссылке-шарингу.
        Поддерживает навигацию по папкам через ?folder=<id>.
        """
        share = get_share_by_token(token)
        if not share:
            return render_template('public_share_invalid.html'), 404

        item = share.file
        if not item:
            return render_template('public_share_invalid.html'), 404

        # Навигация по папкам (для шаринга папок)
        folder_id = request.args.get('folder', type=int)

        # Если шарят файл — показываем его
        if not item.is_folder:
            return render_template(
                'public_share.html',
                share=share,
                item=item,
                folder=None,
                items=None,
                breadcrumbs=None,
                token=token,
            )

        # Шарят папку: если folder_id не задан — показываем саму папку
        if folder_id is None:
            current_folder = item
        else:
            # Ищем внутри папки-шаринга (защита: folder должен быть внутри item)
            current_folder = CloudFile.query.filter_by(
                id=folder_id,
                is_folder=True,
                is_trashed=False,
            ).first()

            if not current_folder:
                return render_template('public_share_invalid.html'), 404

            # Проверяем, что folder — потомок item
            # (иначе можно было бы лазить по чужим папкам)
            if not _is_descendant_of(current_folder, item):
                return render_template('public_share_invalid.html'), 404

        # Список файлов внутри current_folder
        items = list_folder(current_folder.owner_id, parent_id=current_folder.id)

        # Хлебные крошки от item до current_folder
        breadcrumbs = _public_breadcrumbs(item, current_folder, token)

        return render_template(
            'public_share.html',
            share=share,
            item=item,
            folder=current_folder,
            items=items,
            breadcrumbs=breadcrumbs,
            token=token,
        )

    @app.route('/s/<token>/download')
    def public_share_download(token):
        """Скачивание файла, на который создан шаринг."""
        import os
        from flask import current_app, abort

        share = get_share_by_token(token)
        if not share:
            abort(404, description='Ссылка недействительна')

        item = share.file
        if not item or item.is_folder:
            abort(404, description='Это не файл')

        # Собираем путь
        user_dir = os.path.join(
            current_app.config['CLOUD_DATA_DIR'],
            str(item.owner_id),
        )
        file_path = os.path.join(user_dir, item.stored_name)

        # Проверка path traversal
        abs_file = os.path.abspath(file_path)
        abs_dir = os.path.abspath(user_dir)
        if not abs_file.startswith(abs_dir + os.sep):
            abort(403)

        if not os.path.isfile(file_path):
            abort(404, description='Файл отсутствует на диске')

        # Инкремент счётчика
        increment_share_download(share)

        return send_file(
            file_path,
            mimetype=item.mime_type or 'application/octet-stream',
            as_attachment=True,
            download_name=item.name,
            conditional=True,
        )

    @app.route('/s/<token>/download/<int:file_id>')
    def public_share_download_file(token, file_id):
        """Скачивание конкретного файла из папки, доступной по шарингу."""
        import os
        from flask import current_app, abort

        share = get_share_by_token(token)
        if not share:
            abort(404, description='Ссылка недействительна')

        root = share.file
        if not root or not root.is_folder:
            abort(404, description='Это не папка')

        # Ищем файл
        target = CloudFile.query.filter_by(
            id=file_id,
            is_folder=False,
            is_trashed=False,
            owner_id=root.owner_id,
        ).first()

        if not target:
            abort(404, description='Файл не найден')

        # Проверяем, что файл — потомок root
        if not _is_descendant_of(target, root):
            abort(403, description='Доступ запрещён')

        # Путь
        user_dir = os.path.join(
            current_app.config['CLOUD_DATA_DIR'],
            str(root.owner_id),
        )
        file_path = os.path.join(user_dir, target.stored_name)

        abs_file = os.path.abspath(file_path)
        abs_dir = os.path.abspath(user_dir)
        if not abs_file.startswith(abs_dir + os.sep):
            abort(403)

        if not os.path.isfile(file_path):
            abort(404, description='Файл отсутствует на диске')

        increment_share_download(share)

        return send_file(
            file_path,
            mimetype=target.mime_type or 'application/octet-stream',
            as_attachment=True,
            download_name=target.name,
            conditional=True,
        )

        # === API: ОКОНЧАТЕЛЬНОЕ УДАЛЕНИЕ ===

    @app.route('/api/delete-permanent/<int:item_id>', methods=['POST'])
    @login_required
    def api_delete_permanent(item_id):
        """
        Полное удаление: файл с диска + запись из БД.
        Возвращает JSON: {"ok": true, "count": N, "freed_bytes": M} или {"ok": false, "error": "..."}
        """
        ok, result = delete_item_permanently(current_user.id, item_id)

        if not ok:
            return jsonify({'ok': False, 'error': result}), 400

        return jsonify({
            'ok': True,
            'count': result['count'],
            'freed_bytes': result['freed_bytes'],
            'freed_human': format_bytes(result['freed_bytes']),
            'name': result['item'].name,
            'removed_files': result.get('removed_files', 0),
        })


        # === API: СОЗДАНИЕ ПУБЛИЧНОЙ ССЫЛКИ ===

    @app.route('/api/share/<int:item_id>', methods=['POST'])
    @login_required
    def api_share(item_id):
        """
        Создаёт публичную ссылку или возвращает существующую.
        """
        item = get_item(current_user.id, item_id, allow_trashed=False)
        if not item:
            return jsonify({'ok': False, 'error': 'Элемент не найден'}), 404

        # Есть ли уже активная ссылка?
        existing = CloudShare.query.filter_by(
            file_id=item_id,
            created_by_id=current_user.id,
        ).order_by(CloudShare.created_at.desc()).first()

        if existing and not existing.is_expired():
            share = existing
        else:
            ok, result = create_share(current_user.id, item_id)
            if not ok:
                return jsonify({'ok': False, 'error': result}), 400
            share = result

        public_url = url_for('public_share', token=share.token, _external=True)

        return jsonify({
            'ok': True,
            'share': {
                'id': share.id,
                'token': share.token,
                'url': public_url,
                'path': f'/s/{share.token}',
                'file_id': share.file_id,
                'file_name': share.file.name,
                'is_folder': share.file.is_folder,
                'created_at': share.created_at.isoformat() if share.created_at else None,
            },
        })

    @app.route('/api/share/revoke/<int:share_id>', methods=['POST'])
    @login_required
    def api_share_revoke(share_id):
        """Отзывает публичную ссылку."""
        ok, result = revoke_share(current_user.id, share_id)
        if not ok:
            return jsonify({'ok': False, 'error': result}), 404
        return jsonify({'ok': True})

        # === INTERNAL API: создание шары от имени другого пользователя ===
    # Используется framework для прикрепления файлов к статьям.
    # Авторизация через X-Internal-Key + X-User-Id.

    @app.route('/api/internal-share/<int:file_id>', methods=['POST'])
    @csrf.exempt
    def api_internal_share(file_id):
        """
        Создаёт/переиспользует шару на файл от имени пользователя.

        Заголовки:
        - X-Internal-Key: <INTERNAL_API_KEY>  — общий секрет framework↔cloud
        - X-User-Id: <int>                     — id пользователя-владельца

        Ответ — тот же, что у /api/share/<id>.
        """
        import os
        from flask import current_app

        # 1. Проверка ключа
        expected_key = current_app.config.get('INTERNAL_API_KEY') or os.getenv('INTERNAL_API_KEY')
        provided_key = request.headers.get('X-Internal-Key', '')

        if not expected_key:
            return jsonify({'ok': False, 'error': 'INTERNAL_API_KEY не настроен'}), 500

        if provided_key != expected_key:
            return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

        # 2. Получаем user_id из заголовка
        user_id_raw = request.headers.get('X-User-Id', '')
        try:
            user_id = int(user_id_raw)
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'error': 'X-User-Id обязателен'}), 400

        # 3. Проверяем, что пользователь существует
        user = User.query.get(user_id)
        if not user:
            return jsonify({'ok': False, 'error': 'Пользователь не найден'}), 404

        # 4. Проверяем, что файл существует, принадлежит этому пользователю и не в корзине
        item = get_item(user_id, file_id, allow_trashed=False)
        if not item:
            return jsonify({'ok': False, 'error': 'Элемент не найден'}), 404

        # 5. Ищем существующую активную шару или создаём новую
        existing = CloudShare.query.filter_by(
            file_id=file_id,
            created_by_id=user_id,
        ).order_by(CloudShare.created_at.desc()).first()

        if existing and not existing.is_expired():
            share = existing
        else:
            ok, result = create_share(user_id, file_id)
            if not ok:
                return jsonify({'ok': False, 'error': result}), 400
            share = result

        public_url = url_for('public_share', token=share.token, _external=True)

        return jsonify({
            'ok': True,
            'share': {
                'id': share.id,
                'token': share.token,
                'url': public_url,
                'path': f'/s/{share.token}',
                'file_id': share.file_id,
                'file_name': share.file.name,
                'is_folder': share.file.is_folder,
                'created_at': share.created_at.isoformat() if share.created_at else None,
            },
        })

    return app


app = create_app()


if __name__ == '__main__':
    # Локальная разработка — запускаем на 0.0.0.0:5001
    # В продакшене — gunicorn на 127.0.0.1:5001
    app.run(debug=True, host='0.0.0.0', port=5001)
