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
    SENDMAIL = '/usr/sbin/sendmail'

    # Разрешённые команды для systemctl (через sudo)
    ALLOWED_SYSTEMCTL = ['postfix', 'dovecot', 'rspamd']

    # Таймаут для вызовов doveadm/systemctl
    SUBPROCESS_TIMEOUT = 10

    # URL framework — для редиректа на логин
    FRAMEWORK_URL = 'http://192.168.2.19'

    VMAIL_HOME = os.environ.get('VMAIL_HOME') or '/var/vmail'

    # === W47: IMAP ===
    # Master-user: mail-сервис подключается как master*user@domain.
    MAIL_IMAP_HOST = os.environ.get('MAIL_IMAP_HOST') or '127.0.0.1'
    MAIL_IMAP_PORT = int(os.environ.get('MAIL_IMAP_PORT') or 143)
    MAIL_IMAP_MASTER_USER = os.environ.get('MAIL_IMAP_MASTER_USER') or 'master'
    MAIL_IMAP_MASTER_PASSWORD = os.environ.get('MAIL_MASTER_PASSWORD') or ''

    # === W47: отправка ===
    # sendmail -f <from> -t (Postfix, локально)
    MAIL_RATE_LIMIT_PER_HOUR = int(os.environ.get('MAIL_RATE_LIMIT_PER_HOUR') or 100)

    # === W47: пагинация ===
    MAIL_PER_PAGE_DEFAULT = 50
    MAIL_PER_PAGE_MAX = 100

    # === W47: кэш ===
    # SimpleCache — потокобезопасный in-memory кэш (одна машина).
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 30

    # === W47: rate limit ===
    # Хранилище для Flask-Limiter (in-memory; для одного процесса хватает).
    RATELIMIT_STORAGE_URI = 'memory://'