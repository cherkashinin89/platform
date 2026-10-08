# extensions.py - Инициализация расширений Flask
from flask_sqlalchemy import SQLAlchemy  # ORM для работы с БД
from flask_login import LoginManager      # Менеджер аутентификации
from flask_wtf.csrf import CSRFProtect    # Защита от CSRF-атак
from flask_migrate import Migrate

# Создаём экземпляр базы данных (без привязки к приложению)
db = SQLAlchemy()

# Создаём менеджер для управления сессиями пользователей
login_manager = LoginManager()

# Указываем маршрут для перенаправления неавторизованных пользователей
login_manager.login_view = 'login'

# Сообщение, которое увидит пользователь при необходимости входа
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Категория flash-сообщения для стилизации
login_manager.login_message_category = 'warning'

# Создаём экземпляр CSRF-защиты для форм
csrf = CSRFProtect()

migrate = Migrate()