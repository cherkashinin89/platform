# mail/config.py — конфигурация mail-сервиса
import os
from core.config import CoreConfig


class Config(CoreConfig):
    """Конфигурация mail-сервиса."""

    # Порт Gunicorn (внутренний)
    MAIL_PORT = 5004

    # Порт Nginx (внешний) — для редиректов/ссылок
    MAIL_EXTERNAL_PORT = 5003

    # Путь к утилитам
    DOVEADM = '/usr/bin/doveadm'
    SYSTEMCTL = '/usr/bin/systemctl'

    # Разрешённые команды для systemctl (через sudo)
    ALLOWED_SYSTEMCTL = ['postfix', 'dovecot', 'rspamd']

    # Таймаут для вызовов doveadm/systemctl
    SUBPROCESS_TIMEOUT = 10

    # URL framework — для редиректа на логин
    FRAMEWORK_URL = 'http://192.168.2.19'

    VMAIL_HOME = os.environ.get('VMAIL_HOME') or '/var/vmail'