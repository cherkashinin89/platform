# cloud/config.py - Конфигурация cloud
#
# Наследует CoreConfig (общие настройки экосистемы) и добавляет
# специфичное для cloud: путь к файлам облака, лимит загрузки.
import os
from core.config import CoreConfig


class Config(CoreConfig):
    """Конфигурация cloud — общая + специфика."""

    # === Директория для файлов облака ===
    # Используем ОБЩИЙ путь из CoreConfig (CLOUD_DATA_ROOT),
    # чтобы framework и cloud видели одни и те же файлы.
    # CLOUD_DATA_DIR оставлен как alias для обратной совместимости
    # (cloud/app.py и cloud_service.py используют это имя).
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    CLOUD_DATA_DIR = CoreConfig.CLOUD_DATA_ROOT

    # === Загрузка файлов ===
    # Максимальный размер одного файла — 512 МБ
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024

    # === Пагинация (переопределяем) ===
    FILES_PER_PAGE = 50

    # === Приложение ===
    APP_NAME = 'Cloud'