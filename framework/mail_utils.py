# framework/mail_utils.py — вызовы mail-сервиса из framework
import os
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _mail_base_url():
    """Базовый URL mail-сервиса (внутренний)."""
    return current_app.config.get('MAIL_INTERNAL_URL') or 'http://127.0.0.1:5004'


def _headers(user_id=None):
    """Заголовки для внутреннего API mail."""
    key = current_app.config.get('INTERNAL_API_KEY') or os.getenv('INTERNAL_API_KEY')
    h = {'X-Internal-Key': key}
    if user_id is not None:
        h['X-User-Id'] = str(user_id)
    return h


def hash_password(password):
    """
    Запрашивает у mail хэш пароля в формате Dovecot.
    Возвращает (ok, hash_or_error).
    """
    url = f'{_mail_base_url()}/api/internal/hash-password'
    try:
        resp = requests.post(
            url,
            headers=_headers(),
            json={'password': password},
            timeout=5,
        )
    except requests.RequestException as e:
        logger.error(f'mail недоступен: {e}')
        return False, f'mail недоступен: {e}'

    if resp.status_code != 200:
        return False, f'mail вернул {resp.status_code}'

    j = resp.json()
    if not j.get('ok'):
        return False, j.get('error', 'Ошибка mail')
    return True, j['hash']


def get_quota(email):
    """
    Запрашивает у mail использование квоты ящика.
    Возвращает (ok, {'used_bytes': N, 'quota_bytes': M} | error).
    """
    url = f'{_mail_base_url()}/api/internal/quota/{email}'
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
    except requests.RequestException as e:
        logger.error(f'mail недоступен: {e}')
        return False, f'mail недоступен: {e}'

    if resp.status_code != 200:
        return False, f'mail вернул {resp.status_code}'

    j = resp.json()
    if not j.get('ok'):
        return False, j.get('error', 'Ошибка mail')
    return True, {
        'used_bytes': j.get('used_bytes', 0),
        'quota_bytes': j.get('quota_bytes', 0),
    }


def reload_service(service):
    """
    Перезагружает сервис через mail.
    service ∈ {'postfix', 'dovecot', 'rspamd'}.
    Возвращает (ok, error).
    """
    url = f'{_mail_base_url()}/api/internal/reload/{service}'
    try:
        resp = requests.post(url, headers=_headers(), timeout=15)
    except requests.RequestException as e:
        logger.error(f'mail недоступен: {e}')
        return False, f'mail недоступен: {e}'

    if resp.status_code != 200:
        return False, f'mail вернул {resp.status_code}'

    j = resp.json()
    if not j.get('ok'):
        return False, j.get('error', 'Ошибка mail')
    return True, None

def archive_mailbox(email):
    """
    Запрашивает у mail архивацию Maildir ящика.
    Возвращает (ok, archive_path | None | error).
    """
    url = f'{_mail_base_url()}/api/internal/archive-mailbox/{email}'
    try:
        resp = requests.post(url, headers=_headers(), timeout=120)
    except requests.RequestException as e:
        logger.error(f'mail недоступен: {e}')
        return False, f'mail недоступен: {e}'

    if resp.status_code != 200:
        return False, f'mail вернул {resp.status_code}'

    j = resp.json()
    if not j.get('ok'):
        return False, j.get('error', 'Ошибка mail')
    return True, j.get('path')