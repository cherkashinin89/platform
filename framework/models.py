# models.py - Модели базы данных
from datetime import datetime           # Для работы с датами
from flask_login import UserMixin       # Миксин для модели пользователя
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db               # Импорт экземпляра БД
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Промежуточная таблица для связи пользователей и статей (авторы)
article_authors = db.Table('article_authors',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    """Модель пользователя системы"""

    # Уникальный идентификатор пользователя
    id = db.Column(db.Integer, primary_key=True)

    # Имя пользователя (уникальное, обязательно)
    username = db.Column(db.String(80), unique=True, nullable=False)

    # ФИО (полное имя) — опционально
    full_name = db.Column(db.String(200), nullable=True)    
    # Email (уникальный, обязательно)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # Хэш пароля (никогда не храним пароль в открытом виде!)
    password_hash = db.Column(db.String(256), nullable=False)

    # === Роль пользователя ===
    # viewer | user | editor | admin
    role = db.Column(db.String(20), nullable=False, default='user', index=True)

    # Дата регистрации
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

            # === Квота для облачного хранилища ===
    # По умолчанию 1 ГБ. Администратор может изменить в админке.
    quota_bytes = db.Column(
        db.BigInteger,
        nullable=False,
        default=1024 * 1024 * 1024,   # 1 ГБ
    )

    # Связь со статьями (автор может иметь много статей)
    articles = db.relationship('Article', secondary=article_authors,
                               backref='authors', lazy='dynamic')

    # === Константы ролей (для использования в коде) ===
    ROLE_VIEWER = 'viewer'
    ROLE_USER = 'user'
    ROLE_EDITOR = 'editor'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        ('viewer', 'Наблюдатель — только публичная часть'),
        ('user',   'Пользователь — публичная часть + облако + почта'),
        ('editor', 'Редактор — контент в админке без системных настроек'),
        ('admin',  'Администратор — полный доступ'),
    ]

    # === Обратная совместимость: is_admin как свойство ===
    @property
    def is_admin(self):
        """True, если роль == admin. Обратная совместимость со старым кодом."""
        return self.role == self.ROLE_ADMIN

    @property
    def is_editor(self):
        """True для editor и admin (может управлять контентом)."""
        return self.role in (self.ROLE_EDITOR, self.ROLE_ADMIN)

    @property
    def is_user(self):
        """True для любого, кто может пользоваться облаком и почтой."""
        return self.role in (self.ROLE_USER, self.ROLE_EDITOR, self.ROLE_ADMIN)

    @property
    def role_label(self):
        """Человекочитаемое название роли."""
        for value, label in self.ROLE_CHOICES:
            if value == self.role:
                return label.split(' — ')[0]
        return self.role

    def set_password(self, password):
        """Установка пароля с хэшированием"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Проверка пароля"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Article(db.Model):
    """Модель статьи"""
    
    # Уникальный идентификатор статьи
    id = db.Column(db.Integer, primary_key=True)
    
    # Заголовок статьи
    title = db.Column(db.String(200), nullable=False)
    
    # Содержимое статьи (текст)
    content = db.Column(db.Text, nullable=False)
    
    # Краткое описание для анонса
    summary = db.Column(db.String(500))
    
    # Дата создания
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Дата последнего обновления
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Флаг публикации (черновик или опубликовано)
    is_published = db.Column(db.Boolean, default=False)

    # W3: дата перевода в архив (None = не в архиве)
    archived_at = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f'<Article {self.title}>'


class Page(db.Model):
    """Модель статической страницы"""
    
    # Уникальный идентификатор страницы
    id = db.Column(db.Integer, primary_key=True)
    
    # Название страницы
    title = db.Column(db.String(200), nullable=False)
    
    # URL-адрес страницы (уникальный)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    
    # Содержимое страницы (HTML)
    content = db.Column(db.Text, nullable=False)
    
    # Дата создания
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Page {self.title}>'


class MenuItem(db.Model):
    """Модель пункта меню"""
    
    # Уникальный идентификатор пункта меню
    id = db.Column(db.Integer, primary_key=True)
    
    # Отображаемое название
    title = db.Column(db.String(100), nullable=False)
    
    # URL-адрес ссылки
    url = db.Column(db.String(200), nullable=False)
    
    # Порядок сортировки в меню
    order = db.Column(db.Integer, default=0)
    
    # Позиция меню: 'header', 'sidebar', 'footer'
    position = db.Column(db.String(20), default='header')
    
    # Родительский пункт (для вложенных меню)
    parent_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=True)

     # Опциональная связь со страницей (one-to-one)
    page_id = db.Column(
        db.Integer,
        db.ForeignKey('page.id', ondelete='SET NULL'),
        nullable=True,
        unique=True,
    )
    page = db.relationship('Page', backref=db.backref('menu_item', uselist=False))
    
    # Связь с дочерними пунктами
    children = db.relationship('MenuItem', backref=db.backref('parent', remote_side=[id]),
                               lazy='dynamic')
    
    def __repr__(self):
        return f'<MenuItem {self.title}>'
        
class UploadedFile(db.Model):
    """Модель загруженного файла (метаданные)"""

    # Уникальный идентификатор
    id = db.Column(db.Integer, primary_key=True)

    # Оригинальное имя файла (как назвал пользователь)
    original_name = db.Column(db.String(255), nullable=False)

    # Уникальное имя файла на диске (чтобы не было коллизий)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)

    # MIME-тип (например, image/jpeg, application/pdf)
    mime_type = db.Column(db.String(120))

    # Категория файла: image, video, audio, document, archive, other
    file_type = db.Column(db.String(30), nullable=False, default='other')

    # Размер файла в байтах
    size = db.Column(db.Integer, nullable=False, default=0)

    # Расширение файла (без точки): jpg, pdf, mp4
    extension = db.Column(db.String(20))

    # Дата загрузки
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Кто загрузил (внешний ключ на пользователя)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_by = db.relationship('User', backref='uploaded_files')

    # Заметка/описание (необязательно)
    description = db.Column(db.String(500))

    # Имя файла-миниатюры (например, thumb_20260919_abc123.jpg)
    thumbnail_name = db.Column(db.String(255))

    def size_human(self):
        """Человекочитаемый размер: 1.2 MB, 340 KB и т.д."""
        size = self.size or 0
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}' if unit != 'B' else f'{size} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def icon(self):
        """Иконка Bootstrap Icons в зависимости от типа"""
        return {
            'image': 'bi-file-earmark-image',
            'video': 'bi-file-earmark-play',
            'audio': 'bi-file-earmark-music',
            'document': 'bi-file-earmark-text',
            'archive': 'bi-file-earmark-zip',
            'other': 'bi-file-earmark'
        }.get(self.file_type, 'bi-file-earmark')

    def __repr__(self):
        return f'<UploadedFile {self.original_name}>'
        
# models.py - дополнение: Album и Photo

# Промежуточная таблица для связи статей и альбомов (many-to-many)
article_albums = db.Table('article_albums',
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('album.id'), primary_key=True)
)


class Album(db.Model):
    """Фотоальбом (каталог фотографий)"""

    id = db.Column(db.Integer, primary_key=True)

    # Название альбома (тема)
    title = db.Column(db.String(200), nullable=False)

    # URL-идентификатор: /gallery/<slug>
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Описание (необязательно)
    description = db.Column(db.Text)

    # ID обложки — ссылается на Photo (обложку выбираем вручную)
    cover_photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', use_alter=True,
                                                         name='fk_album_cover'))
    cover_photo = db.relationship('Photo', foreign_keys=[cover_photo_id], post_update=True)

    # Флаг публикации: скрытые альбомы не видны на публичной части
    is_published = db.Column(db.Boolean, default=True, index=True)

    # Порядок сортировки в списке
    order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Связь с фотографиями (удаляются каскадом при удалении альбома)
    photos = db.relationship('Photo', backref='album',
                             cascade='all, delete-orphan',
                             foreign_keys='Photo.album_id',
                             order_by='Photo.order')

    # Связь со статьями (many-to-many)
    articles = db.relationship('Article', secondary=article_albums,
                               backref=db.backref('albums', lazy='dynamic'))

    def __repr__(self):
        return f'<Album {self.title}>'


class Photo(db.Model):
    """Фотография в альбоме — ссылка на облачный файл (CloudFile)"""

    id = db.Column(db.Integer, primary_key=True)

    # К какому альбому относится
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=False)

    # Какой облачный файл используется (W3: перешли с uploaded_file на cloud_file)
    file_id = db.Column(db.Integer, db.ForeignKey('cloud_file.id', ondelete='CASCADE'), nullable=False)
    file = db.relationship('CloudFile', foreign_keys=[file_id])

    # Подпись (необязательно)
    caption = db.Column(db.String(300))

    # Порядок сортировки внутри альбома
    order = db.Column(db.Integer, default=0)

    added_at = db.Column(db.DateTime, default=datetime.utcnow)

        # НОВОЕ: фото отмечено для показа в слайдере шапки
    is_featured = db.Column(db.Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f'<Photo {self.id} in {self.album_id}>'

class SiteSettings(db.Model):
    
    #Глобальные настройки сайта.
    #В БД должна быть ровно одна запись — синглтон.

    id = db.Column(db.Integer, primary_key=True)

    # === Идентификация сайта ===
    site_title = db.Column(db.String(200), default='Мой Сайт', nullable=False)
    site_subtitle = db.Column(db.String(300), default='')
    site_description = db.Column(db.String(500), default='')
    site_keywords = db.Column(db.String(300), default='')
    # === Базовые URL для кросс-приложений ===
    # (используются в шапке для ссылок на облако, почту и т.д.)
    site_base_url = db.Column(
        db.String(200),
        default='http://192.168.2.18',
        nullable=False,
    )
    cloud_base_url = db.Column(
        db.String(200),
        default='http://192.168.2.18:5001',
        nullable=False,
    )
    mail_base_url = db.Column(
        db.String(200),
        default='http://192.168.2.18:5002',
        nullable=False,
    )

    # === Элементы интерфейса (вкл/выкл) ===
    show_header = db.Column(db.Boolean, default=True, nullable=False)
    show_header_menu = db.Column(db.Boolean, default=True, nullable=False)
    show_sidebar = db.Column(db.Boolean, default=True, nullable=False)
    show_footer = db.Column(db.Boolean, default=True, nullable=False)

    # === Оформление ===
    # Имя папки в static/themes/ (например, 'default', 'dark', 'blue')
    active_theme = db.Column(db.String(50), default='default', nullable=False)

    # Логотип (ссылка на файл из файлового меню)
    logo_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    logo_file = db.relationship('UploadedFile', foreign_keys=[logo_file_id])

    # Favicon (иконка вкладки)
    favicon_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    favicon_file = db.relationship('UploadedFile', foreign_keys=[favicon_file_id])

    # Показывать ли слайдер в шапке
    show_slider = db.Column(db.Boolean, default=False, nullable=False)
    # Время показа каждого слайда в секундах
    slider_delay_seconds = db.Column(db.Integer, default=5, nullable=False)

    # === W3: Архивация статей ===
    # Через сколько дней после создания статья уходит в архив (0 = не архивировать)
    archive_after_days = db.Column(db.Integer, default=0, nullable=False)
    # Сколько дней хранить архив до удаления (0 = хранить вечно)
    archive_retention_days = db.Column(db.Integer, default=0, nullable=False)

    # === Метаданные ===
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    @classmethod
    def get(cls):
        """
        Возвращает единственную запись настроек.
        Если её нет — создаёт с дефолтными значениями.
        """
        settings = cls.query.first()
        if settings is None:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    def get_theme_path(self):
        """Возвращает имя CSS-файла темы для использования в шаблоне."""
        # Тема должна существовать в static/themes/<name>/style.css
        return f'themes/{self.active_theme}/style.css'

    def __repr__(self):
        return f'<SiteSettings {self.site_title!r}>'

        # Метод для получения фото для слайдера
    def get_slider_photos(self):
        """
        Возвращает до 10 избранных фото из всех альбомов,
        отсортированных по дате добавления (свежие — первыми).
        """
        from models import Photo  # локальный импорт во избежание циклов
        return (
            Photo.query
            .filter_by(is_featured=True)
            .order_by(Photo.added_at.desc())
            .limit(10)
            .all()
        )

# =============================================================
# МОДЕЛИ ОБЛАКА (для чтения из myframework/admin)
# =============================================================
# ВАЖНО: эти модели — ТОЧНАЯ КОПИЯ из mycloud/models.py.
# Они работают с той же БД, но myframework их НЕ мигрирует —
# таблицы созданы миграциями mycloud.
#
# Если меняется структура — менять в ОБОИХ местах.
# =============================================================


class CloudFile(db.Model):
    """Файл или папка в облаке пользователя (read-only для myframework)."""
    __tablename__ = 'cloud_file'

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Relationship на владельца (для отображения в UI админа)
    owner = db.relationship(
        'User',
        foreign_keys=[owner_id],
        backref=db.backref('cloud_files', lazy='dynamic'),
    )
    parent_id = db.Column(db.Integer, db.ForeignKey('cloud_file.id'), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    is_folder = db.Column(db.Boolean, default=False, nullable=False, index=True)
    stored_name = db.Column(db.String(255), unique=True, nullable=True)
    size = db.Column(db.BigInteger, default=0, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_trashed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    trashed_at = db.Column(db.DateTime, nullable=True)

    def size_human(self):
        """Человекочитаемый размер."""
        size = self.size or 0
        if self.is_folder:
            return '—'
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024:
                return f'{size:.1f} {unit}' if unit != 'Б' else f'{size} {unit}'
            size /= 1024
        return f'{size:.1f} ТБ'

    def __repr__(self):
        kind = 'Folder' if self.is_folder else 'File'
        return f'<CloudFile {kind} {self.name}>'


class CloudShare(db.Model):
    """Публичная ссылка на файл/папку облака (read-only для myframework)."""
    __tablename__ = 'cloud_share'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('cloud_file.id'), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    max_downloads = db.Column(db.Integer, default=0, nullable=False)

    def is_expired(self):
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_downloads and self.download_count >= self.max_downloads:
            return True
        return False

    def __repr__(self):
        return f'<CloudShare {self.token}>'



# =============================================================
# W3-РЕФАКТОРИНГ: реестр использования облачных файлов
# =============================================================

class FileUsage(db.Model):
    """
    Реестр использования облачных файлов в контенте.

    Позволяет:
    - запретить удаление файла, пока он привязан к статье/странице/альбому;
    - найти «где используется файл»;
    - автоматически удалять файлы, оставшиеся без использования
      (например, после удаления статьи по сроку архивации).

    entity_type: 'article' | 'page' | 'album' | 'photo'
    """
    __tablename__ = 'file_usage'

    id = db.Column(db.Integer, primary_key=True)

    file_id = db.Column(
        db.Integer,
        db.ForeignKey('cloud_file.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    file = db.relationship('CloudFile', foreign_keys=[file_id])

    entity_type = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # Кто привязал (для аудита). SET NULL — если автор удалён
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )
    user = db.relationship('User', foreign_keys=[user_id])

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint(
            'file_id', 'entity_type', 'entity_id',
            name='uq_file_usage',
        ),
        db.Index('ix_file_usage_entity', 'entity_type', 'entity_id'),
    )

    def __repr__(self):
        return f'<FileUsage file={self.file_id} {self.entity_type}:{self.entity_id}>'


# =============================================================
# W3-РЕФАКТОРИНГ: журнал значимых действий (аудит)
# =============================================================

class AuditLog(db.Model):
    """
    Журнал значимых действий: делегирование файлов, удаление юзера,
    блокировка удаления используемого файла, автоочистка и т.п.
    """
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)

    # Кто выполнил действие (SET NULL, если юзер удалён)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    user = db.relationship('User', foreign_keys=[user_id])

    # Тип действия: 'user_delete_reassign', 'file_auto_purge', 'file_delete_blocked', ...
    action = db.Column(db.String(64), nullable=False, index=True)

    # Что затронуто
    target_type = db.Column(db.String(32), nullable=True)   # 'user', 'file', 'article'
    target_id = db.Column(db.Integer, nullable=True)

    # Детали в JSON (from/to, счётчики, ошибки)
    details = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action} by user={self.user_id} at {self.created_at}>'