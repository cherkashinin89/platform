# mail/imap_client.py — обёртка над imapclient для mail-сервиса (W47)
#
# Схема: каждый запрос открывает новое соединение (open → работа → close).
# Аутентификация — через master-user Dovecot:
#   login = f'{email}*{MASTER_USER}'  (например, test@example.com*master)
#   password = MAIL_MASTER_PASSWORD
#
# Возвращаемые объекты — простые dict'ы, готовые для шаблонов.
import logging
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from flask import current_app
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

logger = logging.getLogger(__name__)


# ============================================================
# Вспомогательные функции
# ============================================================

def _decode_mime_header(value):
    """Декодирует MIME-заголовок (RFC 2047) в строку."""
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _parse_date(value):
    """Парсит дату из заголовка письма. Возвращает datetime или None."""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


def _human_date(dt):
    """Человекочитаемая дата для списка писем."""
    if not dt:
        return ''
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.utcnow()
    delta = now - dt

    if delta.days == 0:
        return dt.strftime('%H:%M')
    if delta.days == 1:
        return 'вчера'
    if delta.days < 7:
        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        return f'{weekdays[dt.weekday()]} {dt.strftime("%H:%M")}'
    return dt.strftime('%d.%m.%Y')


def _make_client(email):
    """
    Создаёт IMAPClient с master-аутентификацией для указанного email.
    Возвращает (client, error).
    """
    cfg = current_app.config
    host = cfg.get('MAIL_IMAP_HOST', '127.0.0.1')
    port = cfg.get('MAIL_IMAP_PORT', 143)
    master_user = cfg.get('MAIL_IMAP_MASTER_USER', 'master')
    master_password = cfg.get('MAIL_IMAP_MASTER_PASSWORD', '')

    if not master_password:
        return None, 'MAIL_MASTER_PASSWORD не задан'

    login = f'{email}*{master_user}'

    try:
        client = IMAPClient(host, port=port, ssl=False, timeout=10)
    except Exception as e:
        logger.exception(f'IMAP connect failed: {host}:{port}')
        return None, f'Не удалось подключиться к IMAP: {e}'

    try:
        client.login(login, master_password)
    except IMAPClientError as e:
        logger.warning(f'IMAP login failed for {login}: {e}')
        try:
            client.logout()
        except Exception:
            pass
        return None, f'Ошибка аутентификации IMAP: {e}'
    except Exception as e:
        logger.exception(f'IMAP login unexpected error for {login}')
        try:
            client.logout()
        except Exception:
            pass
        return None, f'Ошибка IMAP: {e}'

    return client, None


def _safe_close(client):
    """Закрывает IMAP-соединение, глотает ошибки."""
    if not client:
        return
    try:
        client.logout()
    except Exception:
        try:
            client.shutdown()
        except Exception:
            pass


# ============================================================
# Публичный API
# ============================================================

def list_folders(email):
    """
    Возвращает список папок с количеством писем.
    Формат: [{'name': 'INBOX', 'display_name': 'INBOX', 'total': N, 'unread': M}, ...]
    Возвращает (folders_list, error).
    """
    client, err = _make_client(email)
    if err:
        return None, err

    try:
        raw_folders = client.list_folders()
        folders = []

        for flags, delimiter, name in raw_folders:
            try:
                status = client.folder_status(name, ['MESSAGES', 'UNSEEN'])
                total = status.get(b'MESSAGES', 0)
                unread = status.get(b'UNSEEN', 0)
            except Exception:
                total = 0
                unread = 0

            # Человекочитаемое имя (Sent → Отправленные и т.п.)
            display = _folder_display_name(name)

            folders.append({
                'name': name,
                'display_name': display,
                'total': total,
                'unread': unread,
            })

        return folders, None
    except Exception as e:
        logger.exception(f'list_folders failed for {email}')
        return None, f'Ошибка чтения папок: {e}'
    finally:
        _safe_close(client)


def list_messages(email, folder='INBOX', limit=50, offset=0):
    """
    Возвращает список писем в папке (кратко).
    Формат письма:
        {
            'uid': int,
            'subject': str,
            'from_name': str,
            'from_email': str,
            'date': datetime|None,
            'date_human': str,
            'is_read': bool,
            'is_flagged': bool,
            'has_attachments': bool,
        }
    Возвращает (messages_list, total_count, error).
    """
    client, err = _make_client(email)
    if err:
        return None, 0, err

    try:
        client.select_folder(folder, readonly=True)

        # Получаем все UID в папке (по убыванию — новые сверху)
        uids = client.search(['ALL'])
        total = len(uids)

        if not uids:
            return [], 0, None

        # Сортируем по убыванию, берём окно
        uids_sorted = sorted(uids, reverse=True)
        window = uids_sorted[offset:offset + limit]

        if not window:
            return [], total, None

        # Забираем заголовки
        fetch_data = client.fetch(window, [
            'FLAGS',
            'BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)]',
            'RFC822.SIZE',
        ])

        messages = []
        for uid in window:
            data = fetch_data.get(uid, {})
            raw_headers = data.get(b'BODY[HEADER.FIELDS (FROM SUBJECT DATE)]', b'')
            flags = data.get(b'FLAGS', ())

            # Парсим заголовки
            headers = _parse_headers(raw_headers)
            from_raw = headers.get('from', '')
            subject = _decode_mime_header(headers.get('subject', ''))
            date_str = headers.get('date', '')
            dt = _parse_date(date_str)

            from_name, from_email = _parse_from(from_raw)

            messages.append({
                'uid': uid,
                'subject': subject or '(без темы)',
                'from_name': from_name,
                'from_email': from_email,
                'date': dt,
                'date_human': _human_date(dt),
                'is_read': b'\\Seen' in flags,
                'is_flagged': b'\\Flagged' in flags,
                'has_attachments': False,  # TODO: Этап 3.5
            })

        return messages, total, None
    except Exception as e:
        logger.exception(f'list_messages failed for {email}/{folder}')
        return None, 0, f'Ошибка чтения писем: {e}'
    finally:
        _safe_close(client)


def get_message(email, folder, uid):
    """
    Возвращает полное письмо.
    Формат:
        {
            'uid': int,
            'subject': str,
            'from_name': str,
            'from_email': str,
            'to': str,
            'cc': str,
            'date': datetime|None,
            'date_human': str,
            'body_html': str,
            'body_text': str,
            'attachments': [{'filename': str, 'content_type': str, 'size': int, 'part': str}, ...],
        }
    Возвращает (message_dict, error).
    """
    client, err = _make_client(email)
    if err:
        return None, err

    try:
        client.select_folder(folder, readonly=False)  # readonly=False — чтобы отметить Seen

        fetch_data = client.fetch([uid], ['RFC822', 'FLAGS'])
        if uid not in fetch_data:
            return None, 'Письмо не найдено'

        raw = fetch_data[uid].get(b'RFC822', b'')
        if not raw:
            return None, 'Пустое письмо'

        from email import message_from_bytes
        msg = message_from_bytes(raw)

        # Парсим тело и вложения
        body_html, body_text, attachments = _extract_body(msg)

        from_name, from_email_addr = _parse_from(msg.get('From', ''))
        subject = _decode_mime_header(msg.get('Subject', ''))
        dt = _parse_date(msg.get('Date', ''))

        result = {
            'uid': uid,
            'subject': subject or '(без темы)',
            'from_name': from_name,
            'from_email': from_email_addr,
            'to': _decode_mime_header(msg.get('To', '')),
            'cc': _decode_mime_header(msg.get('Cc', '')),
            'date': dt,
            'date_human': dt.strftime('%d.%m.%Y %H:%M') if dt else '',
            'body_html': body_html,
            'body_text': body_text,
            'attachments': attachments,
        }

        return result, None
    except Exception as e:
        logger.exception(f'get_message failed for {email}/{folder}/{uid}')
        return None, f'Ошибка чтения письма: {e}'
    finally:
        _safe_close(client)


# ============================================================
# Внутренние парсеры
# ============================================================

def _folder_display_name(name):
    """Перевод стандартных имён папок."""
    mapping = {
        'INBOX': 'Входящие',
        'Sent': 'Отправленные',
        'Drafts': 'Черновики',
        'Junk': 'Спам',
        'Trash': 'Корзина',
    }
    return mapping.get(name, name)


def _parse_headers(raw):
    """Парсит сырые заголовки в dict (lower-case ключи)."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    result = {}
    current_key = None
    for line in raw.splitlines():
        if not line:
            continue
        if line[0] in ' \t' and current_key:
            result[current_key] += ' ' + line.strip()
        elif ':' in line:
            key, _, value = line.partition(':')
            key = key.strip().lower()
            result[key] = value.strip()
            current_key = key
    return result


def _parse_from(value):
    """Парсит заголовок From: возвращает (name, email)."""
    if not value:
        return '', ''
    value = _decode_mime_header(value)
    # Формат: "Имя <email@example.com>" или "email@example.com"
    if '<' in value and '>' in value:
        name, _, rest = value.partition('<')
        email = rest.partition('>')[0]
        return name.strip().strip('"'), email.strip()
    return '', value.strip()


def _extract_body(msg):
    """
    Извлекает body_html, body_text и список вложений из email.message.Message.
    Возвращает (body_html, body_text, attachments).
    """
    body_html = ''
    body_text = ''
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get('Content-Disposition') or '')

            # Вложение
            if 'attachment' in cdisp:
                filename = part.get_filename()
                if filename:
                    filename = _decode_mime_header(filename)
                payload = part.get_payload(decode=True) or b''
                attachments.append({
                    'filename': filename or 'file',
                    'content_type': ctype,
                    'size': len(payload),
                })
                continue

            # Тело
            if ctype == 'text/html' and not body_html:
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                body_html = payload.decode(charset, errors='replace')
            elif ctype == 'text/plain' and not body_text:
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                body_text = payload.decode(charset, errors='replace')
    else:
        ctype = msg.get_content_type()
        payload = msg.get_payload(decode=True) or b''
        charset = msg.get_content_charset() or 'utf-8'
        text = payload.decode(charset, errors='replace')
        if ctype == 'text/html':
            body_html = text
        else:
            body_text = text

    return body_html, body_text, attachments