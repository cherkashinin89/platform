# config.py - Конфигурация облачного хранилища
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (симлинк на ../myframework/.env)
load_dotenv()

# Базовая директория проекта
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Директория основного приложения (myframework) — там лежит site.db
FRAMEWORK_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'myframework'))


class Config:
    """Базовая конфигурация облака"""

    # === Секретный ключ (общий с myframework) ===
    # Читается из .env (симлинк на ../myframework/.env)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'

    # === База данных — ОБЩАЯ с основным приложением ===
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(FRAMEWORK_DIR, 'site.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # === Директория для файлов облака ===
    CLOUD_DATA_DIR = os.path.join(BASE_DIR, 'cloud_data')

    # === Загрузка файлов ===
    # Максимальный размер одного файла — 512 МБ
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024

    # === Квоты по умолчанию ===
    DEFAULT_QUOTA_BYTES = 1024 * 1024 * 1024   # 1 ГБ

    # === Пагинация ===
    FILES_PER_PAGE = 50

    # === Сессии ===
    # Cookie-сессия Flask-Login
    SESSION_COOKIE_NAME = 'session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE = True   # Включим, когда будет HTTPS

    # === Приложение ===
    APP_NAME = 'MyCloud'
