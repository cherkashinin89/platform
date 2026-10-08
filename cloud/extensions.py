# extensions.py - Инициализация расширений Flask для облака
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# Экземпляр БД (общий site.db с myframework)
db = SQLAlchemy()

# Менеджер аутентификации
login_manager = LoginManager()
login_manager.login_view = 'login'   # если незалогинен — редирект сюда
login_manager.login_message = 'Пожалуйста, войдите, чтобы использовать облако.'
login_manager.login_message_category = 'warning'

# CSRF-защита форм
csrf = CSRFProtect()

# Миграции
migrate = Migrate()
