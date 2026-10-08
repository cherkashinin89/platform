# app.py - Основной файл приложения !! 
import os
from datetime import datetime
from flask import (
    Flask, render_template, redirect, url_for, flash, request,
    jsonify, send_from_directory, send_file, abort, current_app
)
from flask_login import (
    login_user, logout_user, login_required, current_user
)
from auth_utils import admin_required, editor_required, user_required, role_required
from config import Config
from extensions import db, login_manager, csrf, migrate
from forms import (
    LoginForm, UserForm, ArticleForm, PageForm, MenuItemForm,
    UploadFileForm, ArchiveForm, AlbumForm, AlbumPhotosForm,
    SiteSettingsForm
)
from file_utils import (
    get_file_type, guess_mime, make_stored_name,
    human_size, create_archive
)
from image_utils import (
    can_thumbnail, thumbnail_name_for, create_thumbnail
)
from system_stats import get_system_stats
from dotenv import load_dotenv
load_dotenv()
from backup_utils import (
    is_mounted, get_disk_info, create_full_backup, list_backups,
    mount_disk, unmount_disk, sync_buffers
)
from models import (
    User, Article, Page, MenuItem, UploadedFile,
    Album, Photo, SiteSettings, CloudFile, CloudShare,
    FileUsage, AuditLog,
)
from search_service import (
    search_all, search_articles, search_pages, search_files, highlight
)
from slug_utils import slugify, unique_slug
from cloud_utils import (
    get_cloud_file, get_cloud_path, media_url,
    list_cloud_files, user_used_bytes,
)
from content_service import (
    register_file_usages, unregister_file_usages,
    register_album_photos, check_file_usage, find_unused_files,
)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_page():
    """Возвращает номер страницы из ?page=... (минимум 1)"""
    try:
        return max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        return 1

def _send_cloud_file(file):
    """
    Отдаёт облачный файл через send_file.
    Физический путь: CLOUD_DATA_ROOT/<owner_id>/<stored_name>.
    """
    path = get_cloud_path(file)
    if not path or not os.path.exists(path):
        abort(404)
    return send_file(
        path,
        mimetype=file.mime_type or 'application/octet-stream',
        as_attachment=False,
        download_name=file.name,
    )


def _file_is_publicly_usable(file_id):
    """
    Проверяет, привязан ли файл к публичному контенту.
    Публичным считается:
      - любая страница (у Page нет is_published);
      - статья с is_published=True (архив тоже считается публичным);
      - альбом с is_published=True.
    """
    usages = FileUsage.query.filter_by(file_id=file_id).all()
    for u in usages:
        if u.entity_type == 'page':
            if Page.query.get(u.entity_id):
                return True
        elif u.entity_type == 'article':
            a = Article.query.get(u.entity_id)
            if a and a.is_published:
                return True
        elif u.entity_type == 'album':
            al = Album.query.get(u.entity_id)
            if al and al.is_published:
                return True
    return False

def _menu_depth(item, max_depth=10):
    """Вычисляет глубину пункта меню (0 для корня)."""
    depth = 0
    current = item
    while current.parent_id and depth < max_depth:
        current = MenuItem.query.get(current.parent_id)
        if not current:
            break
        depth += 1
    return depth


def _get_menu_parent_choices(exclude_id=None):
    """Возвращает choices для menu_parent_id."""
    query = MenuItem.query.order_by(MenuItem.position, MenuItem.order)
    if exclude_id is not None:
        query = query.filter(MenuItem.id != exclude_id)
    items = query.all()

    choices = [(0, '— без родителя (корневой) —')]
    for m in items:
        depth = _menu_depth(m)
        indent = '— ' * depth
        position_label = {
            'header': 'Верх',
            'sidebar': 'Бок',
            'footer': 'Подвал',
        }.get(m.position, m.position)
        choices.append((m.id, f'{indent}[{position_label}] {m.title}'))
    return choices

def _get_menu_parent_choices_rich(exclude_id=None):
    """
    Возвращает choices с указанием позиции (для JS-фильтра).
    Формат: [(value, label, position), ...]
    """
    query = MenuItem.query.order_by(MenuItem.position, MenuItem.order)
    if exclude_id is not None:
        query = query.filter(MenuItem.id != exclude_id)
    items = query.all()

    result = [(0, '— без родителя —', '')]
    for m in items:
        depth = _menu_depth(m)
        indent = '— ' * depth
        position_label = {
            'header': 'Верх',
            'sidebar': 'Бок',
            'footer': 'Подвал',
        }.get(m.position, m.position)
        result.append((m.id, f'{indent}[{position_label}] {m.title}', m.position))
    return result

def _save_page_menu(page, form):
    """
    Создаёт/обновляет/удаляет MenuItem для страницы.
    """
    existing = page.menu_item

    if form.menu_show.data:
        menu_title = (form.menu_title.data or '').strip() or page.title
        parent_id = form.menu_parent_id.data or None
        if parent_id == 0:
            parent_id = None

        if existing:
            existing.title = menu_title
            existing.url = f'/page/{page.slug}'
            existing.position = form.menu_position.data or 'header'
            existing.parent_id = parent_id
            existing.order = form.menu_order.data or 0
        else:
            menu_item = MenuItem(
                title=menu_title,
                url=f'/page/{page.slug}',
                position=form.menu_position.data or 'header',
                parent_id=parent_id,
                order=form.menu_order.data or 0,
                page_id=page.id,
            )
            db.session.add(menu_item)
    else:
        if existing:
            for child in existing.children:
                child.parent_id = existing.parent_id
            db.session.delete(existing)

def _build_menu_tree(items):
    """
    Строит дерево из плоского списка пунктов меню.
    Возвращает список словарей: [{'item': MenuItem, 'children': [...]}, ...]
    Только корневые пункты (parent_id=None).
    """
    # Группируем детей по parent_id
    by_parent = {}
    for m in items:
        key = m.parent_id
        by_parent.setdefault(key, []).append(m)

    def build(parent_id):
        result = []
        for m in by_parent.get(parent_id, []):
            result.append({
                'item': m,
                'children': build(m.id),
            })
        return result

    return build(None)

# === ФАБРИКА ПРИЛОЖЕНИЯ ===

def create_app(config_class=Config):
    """Создаёт и настраивает экземпляр Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Фильтр Jinja для размеров файлов
    app.jinja_env.filters['human_size_bytes'] = human_size

    # Загрузчик пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # === ПУБЛИЧНЫЕ МАРШРУТЫ ===

    @app.route('/')
    def index():
        """Главная страница сайта с пагинацией статей"""
        page = get_page()
        per_page = app.config['PUBLIC_ARTICLES_PER_PAGE']

        pagination = (
            Article.query
            .filter_by(is_published=True)
            .order_by(Article.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        header_menu = (
            MenuItem.query
            .filter_by(position='header', parent_id=None)
            .order_by(MenuItem.order)
            .all()
        )
        sidebar_menu = (
            MenuItem.query
            .filter_by(position='sidebar', parent_id=None)
            .order_by(MenuItem.order)
            .all()
        )

        return render_template(
            'index.html',
            pagination=pagination,
            articles=pagination.items,
        )

    @app.route('/articles')
    def articles_list():
        """Публичный список всех опубликованных статей с пагинацией"""
        page = get_page()
        per_page = app.config['PUBLIC_ARTICLES_PER_PAGE']

        pagination = (
            Article.query
            .filter_by(is_published=True)
            .order_by(Article.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        return render_template(
            'articles_list.html',
            pagination=pagination,
            articles=pagination.items,
        )

    @app.route('/page/<slug>')
    def show_page(slug):
        """Отображение статической страницы по slug"""
        page = Page.query.filter_by(slug=slug).first_or_404()
        return render_template('page.html', page=page)

    @app.route('/article/<int:id>')
    def show_article(id):
        """Отображение статьи по ID"""
        article = Article.query.get_or_404(id)
        return render_template('article.html', article=article)

    """Поиск"""
    @app.route('/search')
    def search():
        """Публичный поиск по статьям, страницам и файлам"""
        q = request.args.get('q', '').strip()

        if len(q) < 2:
            return render_template('search.html', q=q, results=None, too_short=True)

        results = search_all(q, limit_each=20)

        # Есть ли хоть что-то
        has_any = any(results[k] for k in results)

        return render_template(
            'search.html',
            q=q,
            results=results,
            has_any=has_any,
            highlight=highlight,
        )

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        """Публичная отдача файлов из uploads/"""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # === Публичная отдача облачных файлов ===
    # Доступ:
    #   - владелец файла — всегда;
    #   - админ — всегда;
    #   - остальные — только если файл привязан к опубликованному
    #     контенту (статья is_published / страница (все публичны) /
    #     альбом is_published).
    @app.route('/media/<int:file_id>')
    def serve_media(file_id):
        file = CloudFile.query.get_or_404(file_id)
        if file.is_folder or not file.stored_name:
            abort(404)

        # Доступ: владелец / админ
        if current_user.is_authenticated:
            if current_user.id == file.owner_id or current_user.is_admin:
                return _send_cloud_file(file)

        # Публичный доступ — только если файл привязан к публичному контенту
        if _file_is_publicly_usable(file_id):
            return _send_cloud_file(file)

        # Иначе — 403, чтобы не палить существование файла
        abort(403)

    # === АУТЕНТИФИКАЦИЯ ===

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Страница входа в систему + приём формы из шапки"""
        if current_user.is_authenticated:
            return redirect(url_for('admin_dashboard'))

        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()

            if user and user.check_password(form.password.data):
                login_user(user)
                flash('Вы успешно вошли в систему!', 'success')

                # Если пришли из шапки — возвращаем на ту же страницу
                referrer = request.referrer
                if referrer and url_for('login') not in referrer:
                    return redirect(referrer)

                # Иначе — на следующую или в админку
                next_page = request.args.get('next')
                return redirect(next_page or url_for('admin_dashboard'))

            flash('Неверное имя пользователя или пароль', 'danger')

        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    @editor_required
    def logout():
        """Выход из системы"""
        logout_user()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))

    # === АДМИН-ПАНЕЛЬ ===

    @app.route('/admin/')
    @login_required
    @admin_required
    def admin_dashboard():
        """Главная страница админ-панели"""
        stats = {
            'users': User.query.count(),
            'articles': Article.query.count(),
            'pages': Page.query.count(),
            'menu_items': MenuItem.query.count(),
            'files': UploadedFile.query.count(),
            'albums': Album.query.count(),
        }
        recent_albums = (
            Album.query
            .order_by(Album.created_at.desc())
            .limit(4)
            .all()
        )

        # Статистика сервера (для первоначального рендера)
        server_stats = get_system_stats()

        return render_template('admin/dashboard.html',
                               stats=stats,
                               recent_albums=recent_albums,
                               server_stats=server_stats)

    # --- Управление пользователями ---

    @app.route('/admin/users/')
    @login_required
    @admin_required
    def admin_users():
        """Список пользователей с пагинацией"""
        page = get_page()
        per_page = app.config['USERS_PER_PAGE']

        pagination = (
            User.query
            .order_by(User.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        return render_template(
            'admin/users.html',
            pagination=pagination,
            users=pagination.items
        )

        # === УПРАВЛЕНИЕ ОБЛАКОМ ===

    @app.route('/admin/cloud/')
    @login_required
    @admin_required
    def admin_cloud_users():
        """Список всех пользователей с их квотами и занятым местом в облаке."""
        # Все пользователи
        users = User.query.order_by(User.username.asc()).all()
        # Занятое место по каждому (только файлы, без папок)
        used_rows = (
            db.session.query(CloudFile.owner_id, db.func.sum(CloudFile.size))
            .filter(CloudFile.is_folder == False)  # noqa: E712
            .group_by(CloudFile.owner_id)
            .all()
        )
        used_by_user = {uid: int(total or 0) for uid, total in used_rows}

        # Занятое место в корзине
        trashed_rows = (
            db.session.query(CloudFile.owner_id, db.func.sum(CloudFile.size))
            .filter(
                CloudFile.is_folder == False,   # noqa: E712
                CloudFile.is_trashed == True,   # noqa: E712
            )
            .group_by(CloudFile.owner_id)
            .all()
        )
        trashed_by_user = {uid: int(total or 0) for uid, total in trashed_rows}

        # Собираем данные для шаблона
        users_data = []
        for u in users:
            used = used_by_user.get(u.id, 0)
            trashed = trashed_by_user.get(u.id, 0)
            active = used - trashed
            quota = u.quota_bytes or 0
            percent = round(used / quota * 100, 1) if quota > 0 else 0

            users_data.append({
                'user': u,
                'used': used,
                'used_active': active,
                'trashed': trashed,
                'quota': quota,
                'free': max(0, quota - used),
                'percent': percent,
            })

        # Сортировка по занятому месту (убывание)
        users_data.sort(key=lambda x: x['used'], reverse=True)

        return render_template(
            'admin/cloud_users.html',
            users_data=users_data,
        )

    #Детали пользователя — список файлов + форма квоты#
    @app.route('/admin/cloud/user/<int:user_id>')
    @login_required
    @admin_required
    def admin_cloud_user_detail(user_id):
        """Детали пользователя: файлы, квота, действия."""
        user = User.query.get_or_404(user_id)

        # === Файлы пользователя (только корневые, чтобы не показывать вложенные) ===
        # Полный список с иерархией — через parent_id
        all_items = (
            CloudFile.query
            .filter_by(owner_id=user.id)
            .order_by(
                CloudFile.is_trashed.asc(),
                CloudFile.is_folder.desc(),
                CloudFile.name.asc(),
            )
            .all()
        )

        # === Статистика ===
        used = sum(f.size or 0 for f in all_items if not f.is_folder)
        trashed = sum(
            (f.size or 0) for f in all_items
            if not f.is_folder and f.is_trashed
        )
        used_active = used - trashed
        quota = user.quota_bytes or 0
        free = max(0, quota - used)
        percent = round(used / quota * 100, 1) if quota > 0 else 0

        # === Ссылки пользователя ===
        shares = (
            CloudShare.query
            .filter_by(created_by_id=user.id)
            .order_by(CloudShare.created_at.desc())
            .all()
        )

        return render_template(
            'admin/cloud_user.html',
            user=user,
            items=all_items,
            shares=shares,
            used=used,
            used_active=used_active,
            trashed=trashed,
            quota=quota,
            free=free,
            percent=percent,
        )

    # === СКАЧИВАНИЕ ФАЙЛА ПОЛЬЗОВАТЕЛЯ ===

    @app.route('/admin/cloud/user/<int:user_id>/download/<int:file_id>')
    @login_required
    @admin_required
    def admin_cloud_user_download(user_id, file_id):
        """Скачивание файла пользователя (только admin)."""
        from flask import abort, send_file

        # Проверяем, что файл принадлежит пользователю
        record = CloudFile.query.filter_by(
            id=file_id,
            owner_id=user_id,
            is_folder=False,
        ).first()
        if not record:
            abort(404, description='Файл не найден')

        # Путь к файлу
        user_dir = os.path.join(
            current_app.config.get('CLOUD_DATA_DIR') or
            '/home/admin/apps/mycloud/cloud_data',
            str(user_id),
        )
        file_path = os.path.join(user_dir, record.stored_name)

        # Проверка path traversal
        abs_file = os.path.abspath(file_path)
        abs_dir = os.path.abspath(user_dir)
        if not abs_file.startswith(abs_dir + os.sep):
            abort(403)

        if not os.path.isfile(file_path):
            abort(404, description='Файл отсутствует на диске')

        return send_file(
            file_path,
            mimetype=record.mime_type or 'application/octet-stream',
            as_attachment=True,
            download_name=record.name,
            conditional=True,
        )

    # === ИЗМЕНЕНИЕ КВОТЫ ===

    @app.route('/admin/cloud/user/<int:user_id>/quota', methods=['POST'])
    @login_required
    @admin_required
    def admin_cloud_user_quota(user_id):
        """Изменение квоты пользователя."""
        user = User.query.get_or_404(user_id)

        # Получаем значение квоты в МБ из формы
        quota_mb = request.form.get('quota_mb', type=float)
        if quota_mb is None or quota_mb < 0:
            flash('Неверное значение квоты', 'danger')
            return redirect(url_for('admin_cloud_user_detail', user_id=user_id))

        # Переводим МБ в байты
        quota_bytes = int(quota_mb * 1024 * 1024)

        user.quota_bytes = quota_bytes
        db.session.commit()

        flash(
            f'Квота для «{user.username}» установлена: {quota_mb:.0f} МБ',
            'success'
        )
        return redirect(url_for('admin_cloud_user_detail', user_id=user_id))

    # === ОЧИСТКА КОРЗИНЫ ===

    @app.route('/admin/cloud/user/<int:user_id>/trash', methods=['POST'])
    @login_required
    @admin_required
    def admin_cloud_user_trash(user_id):
        """Полная очистка корзины пользователя."""
        user = User.query.get_or_404(user_id)

        # Находим все элементы в корзине
        trashed = CloudFile.query.filter_by(
            owner_id=user.id,
            is_trashed=True,
        ).all()

        if not trashed:
            flash('Корзина уже пуста', 'info')
            return redirect(url_for('admin_cloud_user_detail', user_id=user_id))

        user_dir = os.path.join(
            current_app.config.get('CLOUD_DATA_DIR') or
            '/home/admin/apps/mycloud/cloud_data',
            str(user.id),
        )

        total_size = 0
        removed_files = 0
        deleted_ids = [f.id for f in trashed]

        # Удаляем физические файлы
        for f in trashed:
            if not f.is_folder and f.stored_name:
                total_size += f.size or 0
                path = os.path.join(user_dir, f.stored_name)
                try:
                    os.remove(path)
                    removed_files += 1
                except FileNotFoundError:
                    pass
                except OSError as e:
                    print(f'[admin-clean-trash] {path}: {e}')

        # Удаляем CloudShare для этих файлов
        CloudShare.query.filter(CloudShare.file_id.in_(deleted_ids)).delete(
            synchronize_session=False
        )

        # Удаляем сами записи
        for f in trashed:
            db.session.delete(f)

        db.session.commit()

        flash(
            f'Корзина «{user.username}» очищена: удалено {removed_files} файлов '
            f'({human_size(total_size)})',
            'success'
        )
        return redirect(url_for('admin_cloud_user_detail', user_id=user_id))

    @app.route('/admin/users/create', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_user_create():
        """Создание нового пользователя"""
        form = UserForm()

        if form.validate_on_submit():
            if User.query.filter_by(username=form.username.data).first():
                flash('Пользователь с таким именем уже существует!', 'danger')
                return render_template(
                    'admin/user_form.html',
                    form=form,
                    title='Создание пользователя'
                )

            if User.query.filter_by(email=form.email.data).first():
                flash('Пользователь с таким email уже существует!', 'danger')
                return render_template(
                    'admin/user_form.html',
                    form=form,
                    title='Создание пользователя'
                )

            if not form.password.data or len(form.password.data) < 6:
                flash('Пароль должен содержать минимум 6 символов!', 'danger')
                return render_template(
                    'admin/user_form.html',
                    form=form,
                    title='Создание пользователя'
                )

            user = User(
                username=form.username.data,
                full_name=(form.full_name.data or '').strip() or None,
                email=form.email.data,
                role=form.role.data,
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            flash(f'Пользователь {user.username} создан!', 'success')
            return redirect(url_for('admin_users'))

        return render_template(
            'admin/user_form.html',
            form=form,
            title='Создание пользователя'
        )

    @app.route('/admin/users/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_user_edit(id):
        """Редактирование пользователя"""
        user = User.query.get_or_404(id)
        form = UserForm(obj=user)

        if form.validate_on_submit():
            existing_username = User.query.filter(
                User.username == form.username.data,
                User.id != user.id
            ).first()
            if existing_username:
                flash('Пользователь с таким именем уже существует!', 'danger')
                return render_template(
                    'admin/user_form.html',
                    form=form,
                    title=f'Редактирование: {user.username}',
                    user=user
                )

            existing_email = User.query.filter(
                User.email == form.email.data,
                User.id != user.id
            ).first()
            if existing_email:
                flash('Пользователь с таким email уже существует!', 'danger')
                return render_template(
                    'admin/user_form.html',
                    form=form,
                    title=f'Редактирование: {user.username}',
                    user=user
                )

            user.username = form.username.data
            user.full_name = (form.full_name.data or '').strip() or None
            user.email = form.email.data
            user.role = form.role.data

            if form.password.data:
                if len(form.password.data) < 6:
                    flash('Пароль должен содержать минимум 6 символов!', 'danger')
                    return render_template(
                        'admin/user_form.html',
                        form=form,
                        title=f'Редактирование: {user.username}',
                        user=user
                    )
                user.set_password(form.password.data)

            db.session.commit()
            flash(f'Пользователь «{user.username}» обновлён!', 'success')
            return redirect(url_for('admin_users'))

        return render_template(
            'admin/user_form.html',
            form=form,
            title=f'Редактирование: {user.username}',
            user=user
        )

    @app.route('/admin/users/<int:id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def admin_user_delete(id):
        """Удаление пользователя"""
        user = User.query.get_or_404(id)

        if user.id == current_user.id:
            flash('Нельзя удалить собственную учётную запись!', 'danger')
            return redirect(url_for('admin_users'))

        username = user.username
        db.session.delete(user)
        db.session.commit()

        flash(f'Пользователь «{username}» удалён.', 'info')
        return redirect(url_for('admin_users'))

    # --- Управление статьями ---

    @app.route('/admin/articles/')
    @login_required
    @editor_required
    def admin_articles():
        """Список статей с пагинацией и поиском"""
        page = get_page()
        per_page = app.config['ARTICLES_PER_PAGE']
        q = request.args.get('q', '').strip()

        query = Article.query
        if q:
            like = f'%{q}%'
            query = query.filter(
                db.or_(
                    Article.title.ilike(like),
                    Article.summary.ilike(like),
                    Article.content.ilike(like),
                )
            )

        pagination = (
            query
            .order_by(Article.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        return render_template(
            'admin/articles.html',
            pagination=pagination,
            articles=pagination.items,
            q=q,
        )

    @app.route('/admin/articles/create', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_article_create():
        form = ArticleForm()

        if form.validate_on_submit():
            article = Article(
                title=form.title.data,
                content=form.content.data,
                summary=form.summary.data,
                is_published=form.is_published.data
            )
            article.authors.append(current_user)

            # Привязка альбомов
            album_ids = request.form.getlist('album_ids', type=int)
            for aid in album_ids:
                album = Album.query.get(aid)
                if album:
                    article.albums.append(album)

            db.session.add(article)
            db.session.commit()

            # W3: регистрируем использование облачных файлов в статье
            try:
                register_file_usages(
                    content_html=article.content,
                    entity_type='article',
                    entity_id=article.id,
                    user_id=current_user.id,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.warning(
                    f'register_file_usages (article create) failed: {e}'
                )

            flash('Статья создана!', 'success')
            return redirect(url_for('admin_articles'))

        # Список всех альбомов для чекбоксов
        all_albums = Album.query.order_by(Album.title).all()
        return render_template('admin/article_form.html',
                               form=form,
                               all_albums=all_albums,
                               selected_album_ids=[],
                               title='Создание статьи')

    @app.route('/admin/articles/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_article_edit(id):
        """Редактирование существующей статьи"""
        article = Article.query.get_or_404(id)
        form = ArticleForm(obj=article)

        if form.validate_on_submit():
            article.title = form.title.data
            article.summary = form.summary.data
            article.content = form.content.data
            article.is_published = form.is_published.data

            # Пересобираем привязки альбомов
            article.albums = []  # очистить
            album_ids = request.form.getlist('album_ids', type=int)
            for aid in album_ids:
                album = Album.query.get(aid)
                if album:
                    article.albums.append(album)

            db.session.commit()

            # обновляем реестр использования облачных файлов
            try:
                register_file_usages(
                    content_html=article.content,
                    entity_type='article',
                    entity_id=article.id,
                    user_id=current_user.id,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.warning(
                    f'register_file_usages (article edit) failed: {e}'
                )

            flash(f'Статья «{article.title}» обновлена!', 'success')
            return redirect(url_for('admin_articles'))

        all_albums = Album.query.order_by(Album.title).all()
        selected_album_ids = [a.id for a in article.albums]
        return render_template('admin/article_form.html',
                               form=form,
                               article=article,
                               all_albums=all_albums,
                               selected_album_ids=selected_album_ids,
                               title=f'Редактирование: {article.title}')

    @app.route('/admin/articles/<int:id>/delete', methods=['POST'])
    @login_required
    @editor_required
    def admin_article_delete(id):
        """Удаление статьи"""
        article = Article.query.get_or_404(id)
        article_title = article.title

        # W3: снимаем реестр использования облачных файлов
        try:
            unregister_file_usages('article', article.id)
        except Exception as e:
            current_app.logger.warning(
                f'unregister_file_usages (article delete) failed: {e}'
            )

        db.session.delete(article)
        db.session.commit()

        flash(f'Статья «{article_title}» удалена.', 'info')
        return redirect(url_for('admin_articles'))

    # --- Управление страницами ---

    @app.route('/admin/pages/')
    @login_required
    def admin_pages():
        """Список страниц с поиском"""
        q = request.args.get('q', '').strip()

        query = Page.query
        if q:
            like = f'%{q}%'
            query = query.filter(
                db.or_(
                    Page.title.ilike(like),
                    Page.content.ilike(like),
                )
            )

        pages = query.all()
        return render_template('admin/pages.html', pages=pages, q=q)

    @app.route('/admin/pages/create', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_page_create():
        """Создание новой страницы"""
        form = PageForm()
        form.menu_parent_id.choices = _get_menu_parent_choices()

        # При GET — дефолт "без родителя"
        if request.method == 'GET':
            form.menu_parent_id.data = 0
            form.menu_order.data = 0

        if form.validate_on_submit():
            slug = (form.slug.data or '').strip()

            if slug:
                # Пользователь ввёл slug вручную — проверяем уникальность
                existing = Page.query.filter_by(slug=slug).first()
                if existing:
                    flash('Страница с таким URL уже существует!', 'danger')
                    return render_template(
                        'admin/page_form.html',
                        form=form,
                        title='Создание страницы',
                    )
            else:
                # Автогенерация
                slug = slugify(form.title.data, allow_cyrillic=True)
                slug = unique_slug(Page, slug)

            page = Page(
                title=form.title.data,
                slug=slug,
                content=form.content.data,
            )

            db.session.add(page)
            db.session.flush()

            _save_page_menu(page, form)

            db.session.commit()

            # W3: регистрируем использование облачных файлов в странице
            try:
                register_file_usages(
                    content_html=page.content,
                    entity_type='page',
                    entity_id=page.id,
                    user_id=current_user.id,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.warning(
                    f'register_file_usages (page create) failed: {e}'
                )

            flash('Страница создана!', 'success')
            return redirect(url_for('admin_pages'))

        return render_template(
            'admin/page_form.html',
            form=form,
            title='Создание страницы',
            menu_parent_choices_rich=_get_menu_parent_choices_rich(),
        )

    @app.route('/admin/pages/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_page_edit(id):
        """Редактирование существующей страницы"""
        page = Page.query.get_or_404(id)
        form = PageForm(obj=page)

        exclude_menu_id = page.menu_item.id if page.menu_item else None
        form.menu_parent_id.choices = _get_menu_parent_choices(exclude_id=exclude_menu_id)

        if request.method == 'GET':
            if page.menu_item:
                form.menu_show.data = True
                form.menu_title.data = page.menu_item.title
                form.menu_position.data = page.menu_item.position
                form.menu_parent_id.data = page.menu_item.parent_id or 0
                form.menu_order.data = page.menu_item.order
            else:
                form.menu_parent_id.data = 0

        if form.validate_on_submit():
            slug = (form.slug.data or '').strip()

            if slug:
                # Пользователь ввёл slug вручную — проверяем уникальность
                existing = Page.query.filter(
                    Page.slug == slug,
                    Page.id != page.id,
                ).first()
                if existing:
                    flash('Страница с таким URL уже существует!', 'danger')
                    return render_template(
                        'admin/page_form.html',
                        form=form,
                        title=f'Редактирование: {page.title}',
                        page=page,
                    )
            else:
                # Автогенерация
                slug = slugify(form.title.data, allow_cyrillic=True)
                slug = unique_slug(Page, slug, exclude_id=page.id)

            page.title = form.title.data
            page.slug = slug
            page.content = form.content.data

            _save_page_menu(page, form)

            db.session.commit()

            # W3: обновляем реестр использования облачных файлов
            try:
                register_file_usages(
                    content_html=page.content,
                    entity_type='page',
                    entity_id=page.id,
                    user_id=current_user.id,
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.warning(
                    f'register_file_usages (page edit) failed: {e}'
                )

            flash(f'Страница «{page.title}» обновлена!', 'success')
            return redirect(url_for('admin_pages'))

        return render_template(
            'admin/page_form.html',
            form=form,
            title=f'Редактирование: {page.title}',
            page=page,
            menu_parent_choices_rich=_get_menu_parent_choices_rich(exclude_id=exclude_menu_id),
        )

    @app.route('/admin/pages/<int:id>/delete', methods=['POST'])
    @login_required
    def admin_page_delete(id):
        """Удаление страницы"""
        page = Page.query.get_or_404(id)
        page_title = page.title

        # W3: снимаем реестр использования облачных файлов
        try:
            unregister_file_usages('page', page.id)
        except Exception as e:
            current_app.logger.warning(
                f'unregister_file_usages (page delete) failed: {e}'
            )

        menu_item = page.menu_item
        if menu_item:
            for child in menu_item.children:
                child.parent_id = menu_item.parent_id
            db.session.delete(menu_item)

        db.session.delete(page)
        db.session.commit()

        flash(f'Страница «{page_title}» удалена.', 'info')
        return redirect(url_for('admin_pages'))

    # --- Управление меню ---

    @app.route('/admin/menu/')
    @login_required
    def admin_menu():
        """Список пунктов меню"""
        menu_items = (
            MenuItem.query
            .order_by(MenuItem.position, MenuItem.order)
            .all()
        )
        return render_template('admin/menu.html', menu_items=menu_items)

    @app.route('/admin/menu/create', methods=['GET', 'POST'])
    @login_required
    def admin_menu_create():
        """Создание пункта меню"""
        form = MenuItemForm()

        parents = (
            MenuItem.query
            .order_by(MenuItem.position, MenuItem.order)
            .all()
        )
        form.parent_id.choices = (
            [(0, '— без родителя —')] +
            [(p.id, f'[{p.position}] {p.title}') for p in parents]
        )

        if form.validate_on_submit():
            menu_item = MenuItem(
                title=form.title.data,
                url=form.url.data,
                order=form.order.data,
                position=form.position.data,
                parent_id=form.parent_id.data if form.parent_id.data else None
            )

            db.session.add(menu_item)
            db.session.commit()

            flash('Пункт меню создан!', 'success')
            return redirect(url_for('admin_menu'))

        return render_template(
            'admin/menu_form.html',
            form=form,
            title='Создание пункта меню'
        )

    @app.route('/admin/menu/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def admin_menu_edit(id):
        """Редактирование пункта меню"""
        item = MenuItem.query.get_or_404(id)
        form = MenuItemForm(obj=item)

        parents = (
            MenuItem.query
            .filter(MenuItem.id != item.id)
            .order_by(MenuItem.position, MenuItem.order)
            .all()
        )
        form.parent_id.choices = (
            [(0, '— без родителя —')] +
            [(p.id, f'[{p.position}] {p.title}') for p in parents]
        )

        if form.validate_on_submit():
            item.title = form.title.data
            item.url = form.url.data
            item.position = form.position.data
            item.order = form.order.data
            item.parent_id = form.parent_id.data if form.parent_id.data else None

            db.session.commit()
            flash(f'Пункт меню «{item.title}» обновлён!', 'success')
            return redirect(url_for('admin_menu'))

        if request.method == 'GET':
            form.parent_id.data = item.parent_id or 0

        return render_template(
            'admin/menu_form.html',
            form=form,
            title=f'Редактирование: {item.title}',
            item=item
        )

    @app.route('/admin/menu/<int:id>/delete', methods=['POST'])
    @login_required
    def admin_menu_delete(id):
        """Удаление пункта меню"""
        item = MenuItem.query.get_or_404(id)

        for child in item.children:
            child.parent_id = None

        title = item.title
        db.session.delete(item)
        db.session.commit()

        flash(f'Пункт меню «{title}» удалён.', 'info')
        return redirect(url_for('admin_menu'))

    # --- Файловый менеджер ---

    @app.route('/admin/files/')
    @login_required
    def admin_files():
        """Список файлов с пагинацией, сортировкой, фильтром и поиском (Python-фильтрация)"""
        page = get_page()
        per_page = app.config['FILES_PER_PAGE']

        sort_by = request.args.get('sort', 'uploaded_at')
        direction = request.args.get('dir', 'desc')
        type_filter = request.args.get('type', 'all')
        q = request.args.get('q', '').strip()

        allowed_sort = {'original_name', 'file_type', 'size', 'uploaded_at'}
        if sort_by not in allowed_sort:
            sort_by = 'uploaded_at'
        if direction not in ('asc', 'desc'):
            direction = 'desc'

        # 1. Забираем ВСЕ файлы (их немного — можно все)
        all_files = UploadedFile.query.all()

        # 2. Фильтр по поиску (Python, регистронезависимо для кириллицы)
        if q:
            q_lower = q.lower()
            all_files = [
                f for f in all_files
                if q_lower in (f.original_name or '').lower()
                or q_lower in (f.description or '').lower()
            ]

        # 3. Счётчики по типам (уже с учётом поиска)
        type_counts = {'all': len(all_files)}
        for t in ['image', 'video', 'audio', 'document', 'archive', 'other']:
            type_counts[t] = sum(1 for f in all_files if f.file_type == t)

        # 4. Общий размер (с учётом поиска)
        total_size = sum(f.size or 0 for f in all_files)

        # 5. Фильтр по типу
        if type_filter != 'all':
            all_files = [f for f in all_files if f.file_type == type_filter]

        # 6. Сортировка
        reverse = (direction == 'desc')
        if sort_by == 'original_name':
            all_files.sort(key=lambda f: (f.original_name or '').lower(), reverse=reverse)
        elif sort_by == 'file_type':
            all_files.sort(key=lambda f: f.file_type or '', reverse=reverse)
        elif sort_by == 'size':
            all_files.sort(key=lambda f: f.size or 0, reverse=reverse)
        else:  # uploaded_at
            all_files.sort(
                key=lambda f: f.uploaded_at or datetime.min,
                reverse=reverse
            )

        # 7. Пагинация вручную
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        page_files = all_files[start:end]

        # 8. Мини-обёртка для пагинации (для совместимости с шаблоном)
        class SimplePagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = max(1, (total + per_page - 1) // per_page)
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None

            def iter_pages(self, left_edge=2, left_current=2,
                           right_current=2, right_edge=2):
                last = 0
                for num in range(1, self.pages + 1):
                    if (num <= left_edge
                            or (self.page - left_current - 1 < num
                                < self.page + right_current)
                            or num > self.pages - right_edge):
                        if last + 1 != num:
                            yield None
                        yield num
                        last = num

        pagination = SimplePagination(page_files, page, per_page, total)

        return render_template(
            'admin/files.html',
            pagination=pagination,
            files=page_files,
            sort_by=sort_by,
            direction=direction,
            type_filter=type_filter,
            type_counts=type_counts,
            total_size=total_size,
            q=q,
        )
    @app.route('/admin/files/upload', methods=['POST'])
    @login_required
    def admin_file_upload():
        """Массовая загрузка файлов из формы"""
        # getlist вернёт список всех файлов из поля name="files"
        files = request.files.getlist('files')

        # Обратная совместимость: если пришёл один файл под именем 'file'
        if not files:
            single = request.files.get('file')
            if single:
                files = [single]

        # Отбрасываем пустые поля
        files = [f for f in files if f and f.filename]

        if not files:
            flash('Файлы не выбраны.', 'warning')
            return redirect(url_for('admin_files'))

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        uploaded = 0
        skipped = 0
        total_size = 0

        for file in files:
            original_name = file.filename
            ext = os.path.splitext(original_name)[1].lstrip('.').lower()

            stored_name = make_stored_name(original_name)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)

            try:
                # 1. Сохраняем файл
                file.save(save_path)
                size = os.path.getsize(save_path)

                # 2. Миниатюра для изображений
                thumb_name = None
                if can_thumbnail(original_name):
                    thumb_name = thumbnail_name_for(stored_name)
                    thumb_path = os.path.join(app.config['UPLOAD_FOLDER'], thumb_name)
                    if not create_thumbnail(save_path, thumb_path):
                        thumb_name = None

                # 3. Запись в БД
                record = UploadedFile(
                    original_name=original_name,
                    stored_name=stored_name,
                    mime_type=guess_mime(original_name),
                    file_type=get_file_type(ext),
                    size=size,
                    extension=ext,
                    uploaded_by_id=current_user.id,
                    thumbnail_name=thumb_name,
                )
                db.session.add(record)
                db.session.commit()

                uploaded += 1
                total_size += size

            except Exception as e:
                # Если что-то не так с одним файлом — пропускаем, но не рвём всю загрузку
                print(f'[upload] Ошибка с файлом {original_name}: {e}')
                skipped += 1
                # Откатываем незакоммиченные изменения для этого файла
                db.session.rollback()
                continue

        # Сообщения пользователю
        if uploaded:
            flash(
                f'Загружено файлов: {uploaded} '
                f'(объём: {human_size(total_size)}).',
                'success'
            )
        if skipped:
            flash(f'Не удалось сохранить файлов: {skipped}.', 'warning')

        return redirect(url_for('admin_files'))

    @app.route('/admin/files/<int:id>/download')
    @login_required
    def admin_file_download(id):
        """Скачивание файла"""
        record = UploadedFile.query.get_or_404(id)
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            record.stored_name,
            as_attachment=True,
            download_name=record.original_name
        )

    @app.route('/admin/files/<int:id>/delete', methods=['POST'])
    @login_required
    def admin_file_delete(id):
        """Удаление файла"""
        record = UploadedFile.query.get_or_404(id)
        path = os.path.join(app.config['UPLOAD_FOLDER'], record.stored_name)

        if os.path.exists(path):
            os.remove(path)

        name = record.original_name
        db.session.delete(record)
        db.session.commit()

        flash(f'Файл «{name}» удалён.', 'info')
        return redirect(url_for('admin_files'))

    @app.route('/admin/files/archive', methods=['GET', 'POST'])
    @login_required
    def admin_files_archive():
        """Архивация файлов за указанный период"""
        form = ArchiveForm()

        if form.validate_on_submit():
            start = datetime.combine(form.date_from.data, datetime.min.time())
            end = datetime.combine(form.date_to.data, datetime.max.time())

            if start > end:
                flash('Дата начала позже даты окончания.', 'danger')
                return render_template('admin/archive_form.html', form=form)

            query = UploadedFile.query.filter(
                UploadedFile.uploaded_at >= start,
                UploadedFile.uploaded_at <= end
            )
            if form.file_type.data != 'all':
                query = query.filter(UploadedFile.file_type == form.file_type.data)

            files = query.all()

            if not files:
                flash('За указанный период файлов не найдено.', 'warning')
                return render_template('admin/archive_form.html', form=form)

            for f in files:
                f.stored_path = os.path.join(
                    app.config['UPLOAD_FOLDER'], f.stored_name
                )

            base_name = (
                f'archive_{form.date_from.data:%Y%m%d}_'
                f'{form.date_to.data:%Y%m%d}'
            )
            archive_path = create_archive(
                files,
                app.config['ARCHIVE_FOLDER'],
                base_name,
                fmt=form.archive_format.data,
                delete_after=form.delete_after.data
            )

            if form.delete_after.data:
                for f in files:
                    db.session.delete(f)
                db.session.commit()

            flash(
                f'Архив создан: {os.path.basename(archive_path)} '
                f'({len(files)} файлов).',
                'success'
            )

            return send_from_directory(
                app.config['ARCHIVE_FOLDER'],
                os.path.basename(archive_path),
                as_attachment=True
            )

        return render_template('admin/archive_form.html', form=form)

    # === ПУБЛИЧНАЯ ГАЛЕРЕЯ ===

    @app.route('/gallery')
    def gallery_index():
        """Список опубликованных альбомов"""
        page = get_page()
        per_page = app.config.get('ALBUMS_PER_PAGE', 12)

        pagination = (
            Album.query
            .filter_by(is_published=True)
            .order_by(Album.order.asc(), Album.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        # Меню — как везде
        header_menu = MenuItem.query.filter_by(position='header', parent_id=None)\
            .order_by(MenuItem.order).all()
        sidebar_menu = MenuItem.query.filter_by(position='sidebar', parent_id=None)\
            .order_by(MenuItem.order).all()

        return render_template('gallery/index.html',
                               pagination=pagination,
                               albums=pagination.items)

    @app.route('/gallery/<slug>')
    def gallery_album(slug):
        """Страница альбома с миниатюрами и каруселью"""
        album = Album.query.filter_by(slug=slug, is_published=True).first_or_404()

        photos = album.photos  # уже отсортированы по order

        header_menu = MenuItem.query.filter_by(position='header', parent_id=None)\
            .order_by(MenuItem.order).all()
        sidebar_menu = MenuItem.query.filter_by(position='sidebar', parent_id=None)\
            .order_by(MenuItem.order).all()

        return render_template('gallery/album.html',
                               album=album,
                               photos=photos)

    # --- Управление альбомами ---

    @app.route('/admin/albums/')
    @login_required
    def admin_albums():
        """Список альбомов в админке"""
        page = get_page()
        per_page = app.config.get('ALBUMS_PER_PAGE', 12)

        pagination = (
            Album.query
            .order_by(Album.order.asc(), Album.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )

        return render_template('admin/albums.html',
                               pagination=pagination,
                               albums=pagination.items)

    @app.route('/admin/albums/create', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_album_create():
        """Создание альбома"""
        form = AlbumForm()

        if form.validate_on_submit():
            slug = (form.slug.data or '').strip()

            if slug:
                # Пользователь ввёл slug вручную — проверяем уникальность
                existing = Album.query.filter_by(slug=slug).first()
                if existing:
                    flash('Альбом с таким URL уже существует!', 'danger')
                    return render_template(
                        'admin/album_form.html',
                        form=form,
                        title='Создание альбома',
                    )
            else:
                # Автогенерация
                slug = slugify(form.title.data, allow_cyrillic=True)
                slug = unique_slug(Album, slug)

            album = Album(
                title=form.title.data,
                slug=slug,
                description=form.description.data,
                is_published=form.is_published.data,
                order=form.order.data or 0,
            )
            db.session.add(album)
            db.session.commit()

            flash(f'Альбом «{album.title}» создан. Добавьте в него фотографии.', 'success')
            return redirect(url_for('admin_album_edit', id=album.id))

        return render_template('admin/album_form.html',
                               form=form, title='Создание альбома')

    @app.route('/admin/albums/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    @editor_required
    def admin_album_edit(id):
        """Редактирование альбома + управление фотографиями"""
        album = Album.query.get_or_404(id)
        form = AlbumForm(obj=album)
        photos_form = AlbumPhotosForm()

        # - изображения из облака.
        # - редактор видит только свои;
        # - админ видит все (для модерации).
        if current_user.is_admin:
            image_files = (
                CloudFile.query
                .filter_by(is_folder=False, is_trashed=False)
                .filter(CloudFile.mime_type.like('image/%'))
                .order_by(CloudFile.created_at.desc())
                .all()
            )
        else:
            image_files = list_cloud_files(
                owner_id=current_user.id,
                file_type='image',
                include_trashed=False,
            )
        photos_form.file_ids.choices = [(f.id, f.name) for f in image_files]

        # === ВЕТКА 1: сохранение свойств альбома ===
        if 'save_album' in request.form:
            if not form.validate_on_submit():
                for errors in form.errors.values():
                    for e in errors:
                        flash(e, 'danger')
                return redirect(url_for('admin_album_edit', id=album.id))

            slug = (form.slug.data or '').strip()

            if slug:
                # Пользователь ввёл slug вручную — проверяем уникальность
                existing = Album.query.filter(
                    Album.slug == slug,
                    Album.id != album.id,
                ).first()
                if existing:
                    flash('Альбом с таким URL уже существует!', 'danger')
                    return redirect(url_for('admin_album_edit', id=album.id))
            else:
                # Автогенерация
                slug = slugify(form.title.data, allow_cyrillic=True)
                slug = unique_slug(Album, slug, exclude_id=album.id)

            album.title = form.title.data
            album.slug = slug
            album.description = form.description.data
            album.is_published = form.is_published.data
            album.order = form.order.data or 0
            db.session.commit()
            flash('Альбом обновлён.', 'success')
            return redirect(url_for('admin_album_edit', id=album.id))

        # === ВЕТКА 2: добавление фотографий ===
        if 'add_photos' in request.form:
            # CSRF-проверка через photos_form
            if not photos_form.validate_on_submit():
                for errors in photos_form.errors.values():
                    for e in errors:
                        flash(e, 'danger')
                return redirect(url_for('admin_album_edit', id=album.id))

            selected = photos_form.file_ids.data or []
            if not selected:
                flash('Не выбрано ни одного файла.', 'warning')
                return redirect(url_for('admin_album_edit', id=album.id))

            added = 0
            # Текущий максимальный order
            max_order = (
                db.session.query(db.func.max(Photo.order))
                .filter_by(album_id=album.id)
                .scalar()
            ) or 0

            added_file_ids = []
            for fid in selected:
                # Не добавлять повторно тот же файл
                if Photo.query.filter_by(album_id=album.id, file_id=fid).first():
                    continue
                max_order += 1
                db.session.add(Photo(
                    album_id=album.id,
                    file_id=fid,
                    order=max_order
                ))
                added_file_ids.append(fid)
                added += 1

            db.session.commit()

            db.session.commit()

            # W3: если у альбома ещё нет обложки — ставим первое фото по order
            if not album.cover_photo_id and added_file_ids:
                first_photo = (
                    Photo.query
                    .filter_by(album_id=album.id)
                    .order_by(Photo.order)
                    .first()
                )
                if first_photo:
                    album.cover_photo_id = first_photo.id
                    db.session.commit()

            # W3: регистрируем использование файлов в альбоме
            try:
                register_album_photos(album.id, added_file_ids, current_user.id)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.warning(
                    f'register_album_photos failed: {e}'
                )

            if added:
                flash(f'Добавлено фотографий: {added}.', 'success')
            else:
                flash('Все выбранные файлы уже есть в альбоме.', 'info')
            return redirect(url_for('admin_album_edit', id=album.id))

        # === GET-запрос или POST без явных кнопок ===
        return render_template('admin/album_form.html',
                               form=form,
                               photos_form=photos_form,
                               album=album,
                               image_files=image_files,
                               title=f'Редактирование: {album.title}')

    @app.route('/admin/albums/<int:id>/delete', methods=['POST'])
    @login_required
    def admin_album_delete(id):
        """Удаление альбома (облачные файлы остаются в облаке)"""
        album = Album.query.get_or_404(id)
        title = album.title

        # W3: снимаем реестр использования файлов
        try:
            unregister_file_usages('album', album.id)
        except Exception as e:
            current_app.logger.warning(
                f'unregister_file_usages (album delete) failed: {e}'
            )

        db.session.delete(album)
        db.session.commit()
        flash(f'Альбом «{title}» удалён.', 'info')
        return redirect(url_for('admin_albums'))

    @app.route('/admin/albums/<int:album_id>/photos/<int:photo_id>/delete', methods=['POST'])
    @login_required
    def admin_album_photo_delete(album_id, photo_id):
        """Удаление фото из альбома (облачный файл остаётся в облаке)"""
        photo = Photo.query.filter_by(id=photo_id, album_id=album_id).first_or_404()
        file_id = photo.file_id

        db.session.delete(photo)
        db.session.commit()

        # W3: снимаем FileUsage для этого файла в этом альбоме
        try:
            FileUsage.query.filter_by(
                file_id=file_id,
                entity_type='album',
                entity_id=album_id,
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.warning(
                f'FileUsage cleanup (album photo delete) failed: {e}'
            )

        flash('Фотография удалена из альбома.', 'info')
        return redirect(url_for('admin_album_edit', id=album_id))

    @app.route('/admin/albums/<int:album_id>/cover/<int:photo_id>', methods=['POST'])
    @login_required
    def admin_album_set_cover(album_id, photo_id):
        """
        W3: звезда — сделать фото обложкой И отправить в слайдер.
        Повторный клик по тому же фото — снять с обложки и из слайдера.
        Лимит слайдера — 10 фото; при превышении самое старое
        (по added_at) вытесняется.
        """
        album = Album.query.get_or_404(album_id)
        photo = Photo.query.filter_by(id=photo_id, album_id=album_id).first_or_404()

        # === Снятие (повторный клик) ===
        if photo.is_featured:
            photo.is_featured = False
            first = (
                Photo.query
                .filter_by(album_id=album_id)
                .order_by(Photo.order)
                .first()
            )
            album.cover_photo_id = first.id if first else None
            db.session.commit()
            flash('Фото убрано из слайдера.', 'info')
            return redirect(url_for('admin_album_edit', id=album_id))

        # === Установка ===
        featured_count = Photo.query.filter_by(is_featured=True).count()
        if featured_count >= 10:
            oldest = (
                Photo.query
                .filter_by(is_featured=True)
                .order_by(Photo.added_at.asc())
                .first()
            )
            if oldest:
                oldest.is_featured = False
                if oldest.album.cover_photo_id == oldest.id:
                    first_in_album = (
                        Photo.query
                        .filter_by(album_id=oldest.album_id)
                        .order_by(Photo.order)
                        .first()
                    )
                    oldest.album.cover_photo_id = (
                        first_in_album.id if first_in_album else None
                    )

        photo.is_featured = True
        album.cover_photo_id = photo.id
        db.session.commit()
        flash('Фото стало обложкой и добавлено в слайдер.', 'success')
        return redirect(url_for('admin_album_edit', id=album_id))

    @app.route('/admin/albums/<int:album_id>/reorder', methods=['POST'])
    @login_required
    def admin_album_reorder(album_id):
        """Сохранение нового порядка фото (перетаскивание, JSON)"""
        data = request.get_json(silent=True) or {}
        order_list = data.get('order', [])
        for idx, photo_id in enumerate(order_list):
            photo = Photo.query.filter_by(id=photo_id, album_id=album_id).first()
            if photo:
                photo.order = idx
        db.session.commit()
        return jsonify({'ok': True})

    # --- API для редактора (TinyMCE) ---

    @app.route('/admin/api/files')
    @login_required
    def admin_api_files():
        """JSON-список файлов для модального окна редактора"""
        type_filter = request.args.get('type', 'all')
        query = UploadedFile.query

        if type_filter != 'all':
            query = query.filter(UploadedFile.file_type == type_filter)

        files = query.order_by(UploadedFile.uploaded_at.desc()).all()

        data = []
        for f in files:
            # Миниатюра: если есть thumbnail_name — используем, иначе оригинал
            thumb_name = f.thumbnail_name or f.stored_name
            thumbnail_url = url_for('uploaded_file', filename=thumb_name)

            data.append({
                'id': f.id,
                'name': f.original_name,
                'url': url_for('admin_file_download', id=f.id),
                'public_url': url_for('uploaded_file', filename=f.stored_name),
                'thumbnail_url': thumbnail_url,                  # ← НОВОЕ
                'type': f.file_type,
                'size': f.size_human(),
                'date': f.uploaded_at.strftime('%d.%m.%Y %H:%M'),
            })

        return jsonify(data)

    @app.route('/admin/api/cloud-files')
    @login_required
    @editor_required
    def admin_api_cloud_files():
        """
        JSON-список облачных файлов для модального окна редактора.

        Логика доступа:
          - админ: видит все файлы всех юзеров, с фильтром ?owner=<id>
          - редактор: только свои
        """
        type_filter = request.args.get('type', 'all')
        owner_param = request.args.get('owner', type=int)

        # База: файлы (не папки), не в корзине
        q = CloudFile.query.filter_by(is_folder=False, is_trashed=False)

        if current_user.is_admin:
            # Админ может фильтровать по владельцу, иначе — все
            if owner_param:
                q = q.filter(CloudFile.owner_id == owner_param)
        else:
            # Редактор — только свои
            q = q.filter(CloudFile.owner_id == current_user.id)

        if type_filter != 'all':
            q = q.filter(CloudFile.mime_type.like(f'{type_filter}/%'))

        files = q.order_by(CloudFile.created_at.desc()).all()

        data = []
        for f in files:
            # Определяем category (image / video / audio / document / archive / other)
            mime = (f.mime_type or '').lower()
            if mime.startswith('image/'):
                ftype = 'image'
            elif mime.startswith('video/'):
                ftype = 'video'
            elif mime.startswith('audio/'):
                ftype = 'audio'
            elif any(x in mime for x in ('zip', 'tar', 'gzip', 'rar', '7z')):
                ftype = 'archive'
            elif any(x in mime for x in ('pdf', 'word', 'excel', 'powerpoint', 'text', 'officedocument')):
                ftype = 'document'
            else:
                ftype = 'other'

            data.append({
                'id': f.id,
                'name': f.name,
                'url': url_for('serve_media', file_id=f.id),
                'public_url': url_for('serve_media', file_id=f.id),
                'thumbnail_url': url_for('serve_media', file_id=f.id)
                    if ftype == 'image' else None,
                'type': ftype,
                'size': f.size_human(),
                'date': f.created_at.strftime('%d.%m.%Y %H:%M'),
                'owner_id': f.owner_id,
                'owner_name': f.owner.username if f.owner else '—',
            })

        return jsonify(data)

    @app.route('/admin/api/upload', methods=['POST'])
    @login_required
    def admin_api_upload():
        """AJAX-загрузка файла из редактора"""
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не передан'}), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Пустое имя файла'}), 400

        original_name = file.filename
        ext = os.path.splitext(original_name)[1].lstrip('.').lower()
        stored_name = make_stored_name(original_name)

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(save_path)
        size = os.path.getsize(save_path)

        record = UploadedFile(
            original_name=original_name,
            stored_name=stored_name,
            mime_type=guess_mime(original_name),
            file_type=get_file_type(ext),
            size=size,
            extension=ext,
            uploaded_by_id=current_user.id,
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({
            'id': record.id,
            'name': record.original_name,
            'url': url_for('admin_file_download', id=record.id),
            'public_url': url_for('uploaded_file', filename=record.stored_name),
            'type': record.file_type,
            'size': record.size_human(),
        })

    @app.route('/admin/api/upload-multiple', methods=['POST'])
    @login_required
    def admin_api_upload_multiple():
        """AJAX-загрузка нескольких файлов (из редактора)"""
        files = request.files.getlist('files')
        files = [f for f in files if f and f.filename]

        if not files:
            return jsonify({'error': 'Файлы не переданы'}), 400

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        results = []
        for file in files:
            original_name = file.filename
            ext = os.path.splitext(original_name)[1].lstrip('.').lower()
            stored_name = make_stored_name(original_name)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)

            file.save(save_path)
            size = os.path.getsize(save_path)

            record = UploadedFile(
                original_name=original_name,
                stored_name=stored_name,
                mime_type=guess_mime(original_name),
                file_type=get_file_type(ext),
                size=size,
                extension=ext,
                uploaded_by_id=current_user.id,
            )
            db.session.add(record)
            db.session.flush()  # получаем record.id до commit

            results.append({
                'id': record.id,
                'name': record.original_name,
                'url': url_for('admin_file_download', id=record.id),
                'public_url': url_for('uploaded_file', filename=record.stored_name),
                'type': record.file_type,
                'size': record.size_human(),
            })

        db.session.commit()

        return jsonify({'uploaded': results})

     # === API СТАТИСТИКИ СИСТЕМЫ ===

    @app.route('/admin/api/system-stats')
    @login_required
    def admin_api_system_stats():
        """JSON с текущими метриками сервера"""
        return jsonify(get_system_stats())

        # === НАСТРОЙКИ САЙТА ===


    @app.route('/admin/settings/sync', methods=['POST'])
    @login_required
    @admin_required
    def admin_settings_sync():
        """Принудительная синхронизация буферов диска"""
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        ok = sync_buffers()
        if ok:
            flash('Буферы синхронизированы с диском.', 'success')
        else:
            flash('Не удалось синхронизировать буферы.', 'warning')

        return redirect(url_for('admin_settings'))

    @app.route('/admin/settings/backup', methods=['POST'])
    @login_required
    @admin_required
    def admin_settings_backup():
        """Запуск полного бэкапа на внешний диск"""
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        project_dir = app.config['BASE_DIR']

        # Запускаем бэкап
        result = create_full_backup(
            project_dir=project_dir,
            dest_root=external_path,
            subdir=app.config['EXTERNAL_BACKUP_SUBDIR'],
            keep_count=app.config['EXTERNAL_BACKUP_KEEP'],
        )

        if result['ok']:
            flash(
                f"Бэкап создан: {result['archive_name']} "
                f"({result['size_mb']} МБ)",
                'success'
            )
        else:
            flash(f"Ошибка бэкапа: {result['error']}", 'danger')

        return redirect(url_for('admin_settings'))

    @app.route('/admin/api/disk-status')
    @login_required
    def admin_api_disk_status():
        """JSON со статусом внешнего диска — для обновления в реальном времени"""
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        mounted = is_mounted(external_path)
        info = get_disk_info(external_path) if mounted else None
        return jsonify({
            'path': external_path,
            'mounted': mounted,
            'disk': info,
        })

    @app.route('/admin/settings/mount', methods=['POST'])
    @login_required
    @admin_required
    def admin_settings_mount():
        """Монтирование внешнего диска"""
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        result = mount_disk(external_path)

        if result['ok']:
            flash(result.get('message', 'Диск смонтирован.'), 'success')
        else:
            flash(f"Ошибка монтирования: {result['error']}", 'danger')

        return redirect(url_for('admin_settings'))

    @app.route('/admin/settings/unmount', methods=['POST'])
    @login_required
    @admin_required
    def admin_settings_unmount():
        """Безопасное отмонтирование внешнего диска"""
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        result = unmount_disk(external_path)

        if result['ok']:
            flash(
                result.get('message', 'Диск отмонтирован. Можно безопасно извлечь.'),
                'success'
            )
        else:
            flash(f"Ошибка отмонтирования: {result['error']}", 'danger')

        return redirect(url_for('admin_settings'))

       #делает настройки доступными во всех шаблонах без явной передачи
    @app.context_processor
    def inject_site_settings():
        """Передаёт настройки сайта во все шаблоны"""
        try:
            return {'site_settings': SiteSettings.get()}
        except Exception:
            # Если таблица ещё не создана — вернём пустую заглушку
            return {'site_settings': None}

    def list_themes():
        """Возвращает список папок тем из static/themes/"""
        themes_dir = os.path.join(app.static_folder, 'themes')
        if not os.path.isdir(themes_dir):
            return ['default']
        themes = sorted([
            name for name in os.listdir(themes_dir)
            if os.path.isdir(os.path.join(themes_dir, name))
        ])
        return themes or ['default']

    @app.context_processor
    def inject_recent_articles():
        """Передаёт последние 5 опубликованных статей во все шаблоны."""
        try:
            articles = (
                Article.query
                .filter_by(is_published=True)
                .order_by(Article.created_at.desc())
                .limit(5)
                .all()
            )
            return {'recent_articles': articles}
        except Exception as e:
            app.logger.warning(f'inject_recent_articles: {e}')
            return {'recent_articles': []}

        #маршрут редактирования настроек:
    @app.route('/admin/settings/', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_settings():
        """Страница настроек сайта: резервное копирование + общие настройки"""
        # === Резервное копирование ===
        external_path = app.config['EXTERNAL_BACKUP_PATH']
        mounted = is_mounted(external_path)
        disk_info = get_disk_info(external_path) if mounted else None
        backups = list_backups(external_path, app.config['EXTERNAL_BACKUP_SUBDIR']) if mounted else []

        # === Общие настройки ===
        settings = SiteSettings.get()
        form = SiteSettingsForm(obj=settings)

        # Заполняем выпадающие списки
        themes = list_themes()
        form.active_theme.choices = [(t, t) for t in themes]

        image_files = UploadedFile.query.filter_by(file_type='image')\
            .order_by(UploadedFile.uploaded_at.desc()).all()
        form.logo_file_id.choices = [(0, '— без логотипа —')] + \
                                    [(f.id, f.original_name) for f in image_files]
        form.favicon_file_id.choices = [(0, '— без favicon —')] + \
                                       [(f.id, f.original_name) for f in image_files]

        # Обработка POST — сохранение настроек
        if form.validate_on_submit():
            settings.site_title = form.site_title.data
            settings.site_subtitle = form.site_subtitle.data or ''
            settings.site_description = form.site_description.data or ''
            settings.site_keywords = form.site_keywords.data or ''
            settings.site_base_url = form.site_base_url.data or 'http://192.168.2.18'
            settings.cloud_base_url = form.cloud_base_url.data or 'http://192.168.2.18:5001'
            settings.mail_base_url = form.mail_base_url.data or 'http://192.168.2.18:5002'
            settings.show_header = form.show_header.data
            settings.show_header_menu = form.show_header_menu.data
            settings.show_sidebar = form.show_sidebar.data
            settings.slider_delay_seconds = form.slider_delay_seconds.data or 5
            settings.show_footer = form.show_footer.data
            settings.show_slider = form.show_slider.data
            settings.active_theme = form.active_theme.data or 'default'
            settings.logo_file_id = form.logo_file_id.data or None
            settings.favicon_file_id = form.favicon_file_id.data or None

            db.session.commit()
            flash('Настройки сохранены.', 'success')
            return redirect(url_for('admin_settings'))

        # Для GET-запроса — подставляем текущие значения
        if request.method == 'GET':
            form.logo_file_id.data = settings.logo_file_id or 0
            form.favicon_file_id.data = settings.favicon_file_id or 0

        return render_template('admin/settings.html',
                               external_path=external_path,
                               mounted=mounted,
                               disk_info=disk_info,
                               backups=backups,
                               form=form,
                               settings=settings)

    def get_slider_photos(limit=10):
        """Возвращает список Photo с is_featured=True (свежие вперёд)"""
        try:
            return (
                Photo.query
                .filter_by(is_featured=True)
                .order_by(Photo.added_at.desc())
                .limit(limit)
                .all()
            )
        except Exception as e:
            app.logger.warning(f'get_slider_photos: {e}')
            return []

    @app.context_processor
    def inject_slider_photos():
        """Делает slider_photos доступными во всех шаблонах"""
        try:
            settings = SiteSettings.get()
            photos = get_slider_photos(10) if settings.show_slider else []
            return {'slider_photos': photos}
        except Exception as e:
            app.logger.warning(f'inject_slider_photos: {e}')
            return {'slider_photos': []}   


    @app.route('/admin/albums/reorder', methods=['POST'])
    @login_required
    @editor_required
    def admin_albums_reorder():
        """Сохранение нового порядка альбомов (JSON)"""
        data = request.get_json(silent=True) or {}
        order_list = data.get('order', [])

        if not isinstance(order_list, list):
            return jsonify({'ok': False, 'error': 'Неверный формат'}), 400

        for idx, album_id in enumerate(order_list):
            album = Album.query.get(album_id)
            if album:
                album.order = idx

        db.session.commit()
        return jsonify({'ok': True, 'count': len(order_list)})  

    @app.context_processor
    def inject_menus():
        """Передаёт меню во все шаблоны автоматически."""
        try:
            header_all = (
                MenuItem.query
                .filter_by(position='header')
                .order_by(MenuItem.order)
                .all()
            )
            sidebar_all = (
                MenuItem.query
                .filter_by(position='sidebar')
                .order_by(MenuItem.order)
                .all()
            )

            # Дерево для верхнего меню
            header_menu_tree = _build_menu_tree(header_all)
            print(f'[DEBUG] header_menu_tree type: {type(header_menu_tree).__name__}, len: {len(header_menu_tree)}')
            if header_menu_tree:
                print(f'[DEBUG] first node type: {type(header_menu_tree[0]).__name__}')
            sidebar_menu_tree = _build_menu_tree(sidebar_all)

            return {
                'header_menu': header_menu_tree,
                'sidebar_menu': sidebar_menu_tree,
            }
        except Exception as e:
            app.logger.warning(f'inject_menus: {e}')
            return {'header_menu': [], 'sidebar_menu': []}

    @app.context_processor
    def inject_now():
        """Передаёт текущий год в шаблоны"""
        from datetime import datetime
        return {'now': datetime.now}

    @app.route('/admin/settings/restart', methods=['POST'])
    @login_required
    @admin_required
    def admin_settings_restart():
        """Перезапуск сервиса myframework через systemd"""
        import subprocess
        import threading
        import time

        def delayed_restart():
            time.sleep(1)
            try:
                result = subprocess.run(
                    ['/usr/bin/sudo', '-n',
                     '/usr/bin/systemctl', 'restart', 'myframework'],
                    capture_output=True,        # ← добавить
                    timeout=30,
                    text=True
                )
                # ← добавить: печатаем всё в stdout gunicorn
                print(f'[restart] rc={result.returncode}')
                print(f'[restart] stdout={result.stdout!r}')
                print(f'[restart] stderr={result.stderr!r}')
            except Exception as e:
                print(f'[restart] Ошибка перезапуска: {e}')

        thread = threading.Thread(target=delayed_restart, daemon=True)
        thread.start()

        return jsonify({'ok': True, 'message': 'Перезапуск запущен'})

    @app.route('/admin/api/service-status')
    @login_required
    def admin_api_service_status():
        """Возвращает статус сервиса myframework"""
        import subprocess

        try:
            result = subprocess.run(
                ['/usr/bin/sudo', '-n',
                 '/usr/bin/systemctl', 'is-active', 'myframework'],
                capture_output=True,
                timeout=5,
                text=True
            )
            active = result.stdout.strip() == 'active'
            return jsonify({'active': active, 'status': result.stdout.strip()})
        except Exception as e:
            return jsonify({'active': False, 'error': str(e)}), 200
    
    return app


# === ЗАПУСК ПРИЛОЖЕНИЯ ===

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['ARCHIVE_FOLDER'], exist_ok=True)

        if User.query.count() == 0:
         admin = User(
            username='admin',
            email='admin@example.com',
            role='admin',
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Создан администратор: admin / admin123')

    app.run(debug=True, host='0.0.0.0', port=5000)