# mail/config.py — конфигурация mail-сервиса
from core.config import CoreConfig


class Config(CoreConfig):
    """Конфигурация mail-сервиса."""

    # Порт Gunicorn (внутренний)
    MAIL_PORT = 5004

    # Префикс таблиц alembic для mail
    # (используется в migrations/env.py — там захардкожен 'alembic_version_mail')