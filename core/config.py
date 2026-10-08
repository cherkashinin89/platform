# core/config.py - Базовая конфигурация экосистемы
#
# Общие настройки для всех сервисов (framework, cloud, mail).
# Каждый проект наследует CoreConfig и переопределяет специфичное.
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня platform/ (на 2 уровня вверх от core/)
# core/config.py → core/ → platform/
_platform_root = Path(__file__).resolve().parent.parent
load_dotenv(_platform_root / '.env')


class CoreConfig:
    """Общая конфигурация для всех сервисов экосистемы."""

    # === Секреты (общие для SSO) ===
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # === База данных (общая для всех сервисов) ===
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # === Сессии (для SSO между сервисами) ===
    SESSION_COOKIE_NAME = 'session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE = True        # включим при HTTPS
    # SESSION_COOKIE_DOMAIN = '.site.ru'  # включим на боевом

    # === Облако (единый путь) ===
    CLOUD_DATA_ROOT = os.environ.get('CLOUD_DATA_ROOT') or \
        '/home/deploy/apps/platform/cloud/cloud_data'
    DEFAULT_QUOTA_BYTES = 1024 * 1024 * 1024   # 1 ГБ

    # === Логин ===
    LOGIN_MESSAGE = 'Пожалуйста, войдите, чтобы продолжить.'

    # === Пагинация (общие дефолты) ===
    PUBLIC_ARTICLES_PER_PAGE = 6
    ARTICLES_PER_PAGE = 10
    USERS_PER_PAGE = 20
    FILES_PER_PAGE = 20
