# models.py - Модели облачного хранилища
#
# ВАЖНО: этот файл работает с ОБЩЕЙ БД site.db.
# Модель User должна быть идентична той, что в myframework/models.py,
# потому что обе работают с одной таблицей.
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db



class User(UserMixin, db.Model):
    """Пользователь (та же таблица, что и в myframework)"""

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    quota_bytes = db.Column(
        db.BigInteger,
        nullable=False,
        default=1024 * 1024 * 1024,   # 1 ГБ
    )    



    # === Константы ролей ===
    ROLE_VIEWER = 'viewer'
    ROLE_USER = 'user'
    ROLE_EDITOR = 'editor'
    ROLE_ADMIN = 'admin'

    # === Свойства ===
    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_editor(self):
        return self.role in (self.ROLE_EDITOR, self.ROLE_ADMIN)

    @property
    def is_user(self):
        """Может ли пользоваться облаком."""
        return self.role in (self.ROLE_USER, self.ROLE_EDITOR, self.ROLE_ADMIN)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

# === МОДЕЛИ ОБЛАКА ===

class CloudFile(db.Model):
    """Файл или папка в облаке пользователя"""
    __tablename__ = 'cloud_file'

    id = db.Column(db.Integer, primary_key=True)

    # Владелец (ссылка на user.id)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True,
    )

    # Родительская папка (None = корень пользователя)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('cloud_file.id'),
        nullable=True,
        index=True,
    )

    # Имя файла или папки, как видит пользователь
    name = db.Column(db.String(255), nullable=False)

    # Папка или файл
    is_folder = db.Column(db.Boolean, default=False, nullable=False, index=True)

    # === Только для файлов ===
    # Уникальное имя на диске (UUID + расширение), чтобы избежать коллизий
    stored_name = db.Column(db.String(255), unique=True, nullable=True)

    # Размер в байтах (0 для папок)
    size = db.Column(db.BigInteger, default=0, nullable=False)

    # MIME-тип (image/jpeg, application/pdf и т.д.)
    mime_type = db.Column(db.String(120), nullable=True)

    # === Общие поля ===
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Мягкое удаление (корзина)
    is_trashed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    trashed_at = db.Column(db.DateTime, nullable=True)

    # === Relationships ===
    # Дочерние элементы (для папок)
    children = db.relationship(
        'CloudFile',
        backref=db.backref('parent', remote_side=[id]),
        cascade='all, delete-orphan',
        lazy='dynamic',
    )

    # Владелец
    owner = db.relationship('User', backref='cloud_files')

    def is_owner(self, user):
        """Проверка, что пользователь — владелец"""
        return user and user.id == self.owner_id

    def size_human(self):
        """Человекочитаемый размер"""
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
    """Публичная ссылка на файл или папку"""
    __tablename__ = 'cloud_share'

    __table_args__ = (
            db.Index('ix_cloud_share_token', 'token', unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Что расшарили
    file_id = db.Column(
        db.Integer,
        db.ForeignKey('cloud_file.id'),
        nullable=False,
        index=True,
    )

    # Уникальный токен ссылки (для URL /s/<token>)
    token = db.Column(db.String(64), nullable=False)

    # Кто создал ссылку
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
    )
    


    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Срок действия (None = бессрочно)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Опциональный пароль (bcrypt-хэш)
    password_hash = db.Column(db.String(256), nullable=True)

    # Счётчик скачиваний
    download_count = db.Column(db.Integer, default=0, nullable=False)

    # Максимум скачиваний (0 = без ограничений)
    max_downloads = db.Column(db.Integer, default=0, nullable=False)

    # === Relationships ===
    file = db.relationship('CloudFile', backref='shares')
    created_by = db.relationship('User')

    def is_expired(self):
        """Истекла ли ссылка"""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_downloads and self.download_count >= self.max_downloads:
            return True
        return False

    def __repr__(self):
        return f'<CloudShare {self.token}>'

# =============================================================
# НАСТРОЙКИ САЙТА (дубликат модели из myframework)
# =============================================================
# ВАЖНО: эта модель работает с той же таблицей site_settings
# в общей БД. Определение должно совпадать с myframework/models.py.

class SiteSettings(db.Model):
    """Глобальные настройки сайта (синглтон)."""
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)

    # === Идентификация ===
    site_title = db.Column(db.String(200), default='Мой Сайт', nullable=False)
    site_subtitle = db.Column(db.String(300), default='')
    site_description = db.Column(db.String(500), default='')
    site_keywords = db.Column(db.String(300), default='')

    # === Базовые URL (для кросс-приложений) ===
    site_base_url = db.Column(db.String(200), nullable=False, default='http://192.168.2.18')
    cloud_base_url = db.Column(db.String(200), nullable=False, default='http://192.168.2.18:5001')
    mail_base_url = db.Column(db.String(200), nullable=False, default='http://192.168.2.18:5002')

    # === Элементы интерфейса ===
    show_header = db.Column(db.Boolean, default=True, nullable=False)
    show_header_menu = db.Column(db.Boolean, default=True, nullable=False)
    show_sidebar = db.Column(db.Boolean, default=True, nullable=False)
    show_footer = db.Column(db.Boolean, default=True, nullable=False)

    # === Оформление ===
    active_theme = db.Column(db.String(50), default='default', nullable=False)
    logo_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))
    favicon_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'))

    # === Слайдер ===
    show_slider = db.Column(db.Boolean, default=False, nullable=False)
    slider_delay_seconds = db.Column(db.Integer, default=5, nullable=False)

    # === Метаданные ===
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    @classmethod
    def get(cls):
        """Возвращает единственную запись настроек. Если её нет — создаёт."""
        settings = cls.query.first()
        if settings is None:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f'<SiteSettings {self.site_title!r}>'