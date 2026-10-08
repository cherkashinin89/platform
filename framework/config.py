# config.py - Конфигурация приложения
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env ДО чтения Config
load_dotenv()

class Config:
    """Базовый класс конфигурации"""
    
    # Секретный ключ для сессий и CSRF-защиты
    # В продакшене должен быть сложным и храниться в переменных окружения
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Путь к базе данных SQLite (для разработки на Windows)
    # В продакшене замените на PostgreSQL или MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'site.db')
    
    # Отключаем отслеживание модификаций для экономии памяти
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
       # === Директории файлового менеджера ===

    # Базовая директория проекта
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Куда складывать загруженные файлы
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # Куда складывать архивы
    ARCHIVE_FOLDER = os.path.join(BASE_DIR, 'archives')

    # Максимальный размер одного файла — 32 МБ
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024

    # Разрешённые расширения (пустой список = разрешить все)
    ALLOWED_EXTENSIONS = set()

    # === Внешний накопитель для бэкапов ===
    EXTERNAL_BACKUP_PATH = os.environ.get('EXTERNAL_BACKUP_PATH') or '/mnt/backup'

    # Сколько последних архивов хранить на внешнем диске
    EXTERNAL_BACKUP_KEEP = 10

    # Название папки для бэкапов на внешнем диске
    EXTERNAL_BACKUP_SUBDIR = 'myframework'
    
    # === Пагинация ===
    ARTICLES_PER_PAGE = 10      # статей в админке на странице
    FILES_PER_PAGE = 20         # файлов на странице
    USERS_PER_PAGE = 20         # пользователей на странице
    PUBLIC_ARTICLES_PER_PAGE = 6  # статей на главной (публично)

    # === W3: Облачное хранилище (общая БД с mycloud) ===
    # Физический путь к cloud_data/ (общий для myframework и mycloud)
    CLOUD_DATA_ROOT = os.environ.get('CLOUD_DATA_ROOT') or '/home/deploy/apps/mycloud/cloud_data'
    
