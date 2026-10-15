# core/extensions.py - Общие расширения Flask
#
# Единый набор расширений для всех сервисов экосистемы.
# Импортируются так:
#     from core.extensions import db, login_manager, csrf, migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Единый экземпляр БД для всей экосистемы (общая БД)
db = SQLAlchemy()

# Менеджер аутентификации
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите, чтобы продолжить.'
login_manager.login_message_category = 'warning'

# CSRF-защита форм
csrf = CSRFProtect()

# Миграции Alembic
migrate = Migrate()

# Кэш в памяти (W47: список писем TTL 30 сек, статус папок TTL 60 сек)
cache = Cache()

# Rate limit (W47: 100 писем/час на пользователя)
limiter = Limiter(key_func=get_remote_address)