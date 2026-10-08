# core/extensions.py - Общие расширения Flask
#
# Единый набор расширений для всех сервисов экосистемы.
# Импортируются так:
#     from core.extensions import db, login_manager, csrf, migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

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
