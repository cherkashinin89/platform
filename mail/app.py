# mail/app.py — минимальный каркас для миграций
from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader
import os

from config import Config
from core.extensions import db, login_manager, migrate


def create_app(config_class=Config):
    """Создаёт и настраивает экземпляр Flask (минимальный)."""
    app = Flask(__name__)
    app.config.from_object(config_class)

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
    migrate.init_app(app, db)

    # Загрузчик пользователя (пока минимально)
    from core.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app


app = create_app()