cd /home/deploy/apps/platform/core

cat > models.py << 'MODELS_EOF'
# core/models.py - Модели базы данных (общие для всей экосистемы)
#
# Единый источник правды: User, Article, Page, MenuItem, UploadedFile,
# Album, Photo, CloudFile, CloudShare, SiteSettings, FileUsage, AuditLog.
#
# Импорт: from core.models import User, Article, CloudFile, ...
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from core.extensions import db


# ============================================================
# Промежуточные таблицы
# ============================================================

# Авторы статей (M2M User↔Article)
article_authors = db.Table(
    'article_authors',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True),
)

# Альбомы статей (M2M Article↔Album)
article_albums = db.Table(
    'article_albums',
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('album.id'), primary_key=True),
)


# ============================================================
# Пользователь
# ============================================================

class User(UserMixin, db.Model):
    """Модель пользователя системы."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # viewer | user | editor | admin
    role = db.Column(db.String(20), nullable=False, default='user', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Квота облачного хранилища (байты)
    quota_bytes = db.Column(
        db.BigInteger,
        nullable=False,
        default=1024 * 1024 * 1024,   # 1 ГБ
    )

    # Связь со статьями (M2M)
    articles = db.relationship('Article', secondary=article_authors,
                               backref='authors', lazy='dynamic')

    # === Константы ролей ===
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

    @property
    def is_admin(self):
        """True, если роль == admin."""
        return self.role == self.ROLE_ADMIN

    @property
    def is_editor(self):
        """True для editor и admin."""
        return self.role in (self.ROLE_EDITOR, self.ROLE_ADMIN)

    @property
    def is_user(self):
        """True для всех, кто может пользоваться облаком и почтой."""
        return self.role in (self.ROLE_USER, self.ROLE_EDITOR, self.ROLE_ADMIN)

    @property
    def role_label(self):
        """Человекочитаемое название роли."""
        for value, label in self.ROLE_CHOICES:
            if value == self.role:
                return label.split(' — ')[0]
        return self.role

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# ============================================================
# Контент: Article, Page, MenuItem, UploadedFile
# ============================================================

class Article(db.Model):
    """Модель статьи."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False)

    # W3: дата перевода в архив (None = не в архиве)
    archived_at = db.Column(db.DateTime, nullable=True, index=True)

    def __repr__(self):
        return f'<Article {self.title}>'


class Page(db.Model):
    """Модель статической страницы."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Page {self.title}>'


class MenuItem(db.Model):
    """Модель пункта меню."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0)
    position = db.Column(db.String(20), default='header')  # header | sidebar | footer
    parent_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=True)

    # Опциональная связь со страницей (one-to-one)
    page_id = db.Column(
        db.Integer,
        db.ForeignKey('page.id', ondelete='SET NULL'),
        nullable=True,
        unique=True,
    )
    page = db.relationship('Page', backref=db.backref('menu_item', uselist=False))

    children = db.relationship(
        'MenuItem',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic',
    )

    def __repr__(self):
        return f'<MenuItem {self.title}>'


class UploadedFile(db.Model):
    """Модель загруженного файла (системные файлы: лого, favicon, вложения)."""

    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(120))
    file_type = db.Column(db.String(30), nullable=False, default='other')
    size = db.Column(db.Integer, nullable=False, default=0)
    extension = db.Column(db.String(20))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_by = db.relationship('User', backref='uploaded_files')

    description = db.Column(db.String(500))
    thumbnail_name = db.Column(db.String(255))

    def size_human(self):
        size = self.size or 0
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f'{size:.1f} {unit}' if unit != 'B' else f'{size} {unit}'
            size /= 1024
        return f'{size:.1f} TB'

    def icon(self):
        return {
            'image': 'bi-file-earmark-image',
            'video': 'bi-file-earmark-play',
            'audio': 'bi-file-earmark-music',
            'document': 'bi-file-earmark-text',
            'archive': 'bi-file-earmark-zip',
            'other': 'bi-file-earmark',
        }.get(self.file_type, 'bi-file-earmark')

    def __repr__(self):
        return f'<UploadedFile {self.original_name}>'


# ============================================================
# Галерея: Album, Photo
# ============================================================

class Album(db.Model):
    """Фотоальбом."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)

    cover_photo_id = db.Column(
        db.Integer,
        db.ForeignKey('photo.id', use_alter=True, name='fk_album_cover'),
    )
    cover_photo = db.relationship('Photo', foreign_keys=[cover_photo_id], post_update=True)

    is_published = db.Column(db.Boolean, default=True, index=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    photos = db.relationship(
        'Photo',
        backref='album',
        cascade='all, delete-orphan',
        foreign_keys='Photo.album_id',
        order_by='Photo.order',
    )

    articles = db.relationship(
        'Article',
        secondary=article_albums,
        backref=db.backref('albums', lazy='dynamic'),
    )

    def __repr__(self):
        return f'<Album {self.title}>'


class Photo(db.Model):
    """Фотография в альбоме — ссылка на облачный файл (CloudFile)."""

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=False)

    # W3: облачный файл
    file_id = db.Column(
        db.Integer,
        db.ForeignKey('cloud_file.id', ondelete='CASCADE'),
        nullable=False,
    )
    file = db.relationship('CloudFile', foreign_keys=[file_id])

    caption = db.Column(db.String(300))
    order = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Фото отмечено для показа в слайдере шапки
    is_featured = db.Column(db.Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f'<Photo {self.id} in {self.album_id}>'


# ============================================================
# Настройки сайта
# ============================================================

class SiteSettings(db.Model):
    """Глобальные настройки сайта (синглтон)."""

    id = db.Column(db.Integer, primary_key=True)

    # === Идентификация ===
    site_title = db.Column(db.String(200), default='Мой Сайт', nullable=False)
    site_subtitle = db.Column(db.String(300), default='')
    site_description = db.Column(db.String(500), default='')
    site_keywords = db.Column(db.String(300), default='')

    # === Базовые URL для кросс-приложений ===
    site_base_url = db.Column(db.String(200), default='http://192.168.2.19', nullable=False)
    cloud_base_url = db.Column(db.String(200), default='http://192.168.2.19:5001', nullable=False)
    mail_base_url = db.Column(db.String(200), default='http://192.168.2.19:5002', nullable=False)

    # === Элементы интерфейса ===
    show_header = db.Column(db.Boolean, default=True, nullable=False)
    show_header_menu = db.Column(db.Boolean, default=True, nullable=False)
    show_sidebar = db.Column(db.Boolean, default=True, nullable=False)
    show_footer = db.Column(db.Boolean, default=True, nullable=False)

    # === Оформление ===
    active_theme = db.Column(db.String(50), default='default', nullable=False)

    logo_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    logo_file = db.relationship('UploadedFile', foreign_keys=[logo_file_id])

    favicon_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    favicon_file = db.relationship('UploadedFile', foreign_keys=[favicon_file_id])

    # === Слайдер ===
    show_slider = db.Column(db.Boolean, default=False, nullable=False)
    slider_delay_seconds = db.Column(db.Integer, default=5, nullable=False)

    # === W3: Архивация статей ===
    archive_after_days = db.Column(db.Integer, default=0, nullable=False)
    archive_retention_days = db.Column(db.Integer, default=0, nullable=False)

    # === Метаданные ===
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        """Возвращает единственную запись настроек. Если её нет — создаёт."""
        settings = cls.query.first()
        if settings is None:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    def get_theme_path(self):
        """Возвращает путь к CSS-файлу активной темы."""
        return f'themes/{self.active_theme}/style.css'

    def get_slider_photos(self):
        """До 10 избранных фото, отсортированных по дате добавления."""
        return (
            Photo.query
            .filter_by(is_featured=True)
            .order_by(Photo.added_at.desc())
            .limit(10)
            .all()
        )

    def __repr__(self):
        return f'<SiteSettings {self.site_title!r}>'


# ============================================================
# Облако: CloudFile, CloudShare
# ============================================================

class CloudFile(db.Model):
    """Файл или папка в облаке пользователя."""

    __tablename__ = 'cloud_file'

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
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

    # Владелец
    owner = db.relationship(
        'User',
        foreign_keys=[owner_id],
        backref=db.backref('cloud_files', lazy='dynamic'),
    )

    # Дочерние элементы (для папок)
    children = db.relationship(
        'CloudFile',
        backref=db.backref('parent', remote_side=[id]),
        cascade='all, delete-orphan',
        lazy='dynamic',
    )

    def is_owner(self, user):
        """Проверка, что пользователь — владелец."""
        return user and user.id == self.owner_id

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
    """Публичная ссылка на файл/папку облака."""

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

    file = db.relationship('CloudFile', backref='shares')
    created_by = db.relationship('User')

    def is_expired(self):
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_downloads and self.download_count >= self.max_downloads:
            return True
        return False

    def __repr__(self):
        return f'<CloudShare {self.token}>'


# ============================================================
# W3: реестр использования и аудит
# ============================================================

class FileUsage(db.Model):
    """
    Реестр использования облачных файлов в контенте.

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


class AuditLog(db.Model):
    """Журнал значимых действий (аудит)."""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    user = db.relationship('User', foreign_keys=[user_id])

    action = db.Column(db.String(64), nullable=False, index=True)
    target_type = db.Column(db.String(32), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action} by user={self.user_id} at {self.created_at}>'
MODELS_EOF
