# framework/config.py - Конфигурация framework
#
# Наследует CoreConfig (общие настройки экосистемы) и добавляет
# специфичное для framework: uploads/, archives/, бэкапы.
import os
from core.config import CoreConfig


class Config(CoreConfig):
    """Конфигурация framework — общая + специфика."""

    # === Директории framework ===
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Куда складывать системные файлы (лого, favicon, вложения)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # Куда складывать архивы файлового менеджера
    ARCHIVE_FOLDER = os.path.join(BASE_DIR, 'archives')

    # Максимальный размер одного файла — 32 МБ
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024

    # Разрешённые расширения (пусто = все)
    ALLOWED_EXTENSIONS = set()

    # === Бэкапы (только framework делает бэкапы) ===
    EXTERNAL_BACKUP_PATH = os.environ.get('EXTERNAL_BACKUP_PATH') or '/mnt/backup'
    EXTERNAL_BACKUP_KEEP = 10
    EXTERNAL_BACKUP_SUBDIR = 'framework'