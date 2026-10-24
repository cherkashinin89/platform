# mail/imap_client.py — обёртка над imapclient для mail-сервиса (W47)
#
# Схема: каждый запрос открывает новое соединение (open → работа → close).
# Аутентификация — через master-user Dovecot:
#   login = f'{email}*{MASTER_USER}'  (например, test@example.com*master)
#   password = MAIL_MASTER_PASSWORD
#
# Возвращаемые объекты — простые dict'ы, готовые для шаблонов.
import os
import logging
import bleach
import mimetypes
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from flask import current_app
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
from core.extensions import cache

logger = logging.getLogger(__name__)


# ============================================================
# Вспомогательные функции
# ============================================================

def _decode_mime_header(value):
    if not value:
        return ''
    try:
        # decode_header возвращает список (bytes|str, charset)
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                decoded.append(part)
        return ''.join(decoded)
    except Exception:
        return str(value) if value else ''

def _decode_mime_header_safe(value):
    """Декодирует MIME-заголовок с обходом суррогатных символов."""
    if not value:
        return ''
    if isinstance(value, str):
        try:
            raw_bytes = value.encode('utf-8', errors='surrogateescape')
            decoded = raw_bytes.decode('utf-8', errors='replace')
        except Exception:
            decoded = value
    else:
        decoded = value

    if '=?' in decoded:
        return _decode_mime_header(decoded)
    return decoded


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

        # W47: извлекаем Subject из сырых байтов (до парсинга email)
        import re
        import email.header

        subject = ''
        # Ищем строку "Subject: ..." в сырых байтах (до первой пустой строки)
        # Разделитель заголовков — \r\n\r\n или \n\n (универсально)
        if b'\r\n\r\n' in raw:
            header_block = raw.split(b'\r\n\r\n', 1)[0]
        else:
            header_block = raw.split(b'\n\n', 1)[0]
        match = re.search(rb'^Subject:\s*(.+?)(?=\r?\n\S)', header_block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            raw_subject_bytes = match.group(1).strip()
            # Если MIME-encoded (=?utf-8?...?=)
            if b'=?' in raw_subject_bytes:
                decoded_parts = email.header.decode_header(raw_subject_bytes.decode('utf-8', errors='replace'))
                for part, charset in decoded_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(charset or 'utf-8', errors='replace')
                    else:
                        subject += part
            else:
                # Иначе — просто UTF-8
                subject = raw_subject_bytes.decode('utf-8', errors='replace')
        else:
            # Fallback: через email.Message
            subject = _decode_mime_header(msg.get('Subject', ''))

        # W47: нормализация строки (убираем суррогаты перед кэшированием)
        subject = subject.encode('utf-8', errors='ignore').decode('utf-8')

        from_name, from_email_addr = _parse_from(msg.get('From', ''))
        dt = _parse_date(msg.get('Date', ''))

        # Парсим тело и вложения
        body_html, body_text, attachments = _extract_body(msg)

        result = {
            'uid': uid,
            'subject': subject or '(без темы)',
            'from_name': from_name,
            'from_email': from_email_addr,
            'to': _decode_mime_header_safe(msg.get('To', '')),
            'cc': _decode_mime_header_safe(msg.get('Cc', '')),
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
            cte = part.get('Content-Transfer-Encoding')
            # Вложение
            if 'attachment' in cdisp:
                # Имя из Content-Disposition или Content-Type
                filename = part.get_filename()
                if not filename:
                    filename = part.get_param('name')
                if filename:
                    filename = _decode_mime_header(filename)
                else:
                    # Fallback: file_<index>.<ext>
                    ext = mimetypes.guess_extension(ctype) or ''
                    filename = f'file{ext}'

                payload = part.get_payload(decode=True) or b''
                import base64
                attachments.append({
                    'filename': filename,
                    'content_type': ctype,
                    'size': len(payload),
                    'data_b64': base64.b64encode(payload).decode('ascii'),
                })
                continue

            # Тело
            if ctype == 'text/html' and not body_html:
                payload = part.get_payload(decode=True)
                if payload is None:
                    payload = part.get_payload().encode('utf-8')
                charset = part.get_content_charset() or 'utf-8'
                body_html = payload.decode(charset, errors='replace')
            elif ctype == 'text/plain' and not body_text:
                payload = part.get_payload(decode=True)
                if payload is None:
                    payload = part.get_payload().encode('utf-8')
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

    # === W47: санитизация HTML через bleach ===
    if body_html:
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code', 'dd', 'del',
            'div', 'dl', 'dt', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'hr', 'i', 'img', 'ins', 'kbd', 'li', 'ol', 'p', 'pre', 'q',
            's', 'samp', 'small', 'span', 'strike', 'strong', 'sub', 'sup',
            'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'tt', 'u', 'ul',
        ]
        allowed_attrs = {
            '*': ['class', 'style', 'id', 'align', 'valign', 'width', 'height'],
            'a': ['href', 'title', 'target', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'table': ['border', 'cellpadding', 'cellspacing', 'width', 'style'],
            'td': ['colspan', 'rowspan', 'width', 'valign', 'align', 'style'],
            'th': ['colspan', 'rowspan', 'width', 'valign', 'align', 'style'],
        }
        allowed_protocols = ['http', 'https', 'mailto', 'cid', 'data']
        body_html = bleach.clean(
            body_html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=allowed_protocols,
            strip=True,
        )
        # Принудительно: ссылки — target="_blank" rel="noopener noreferrer"
        def _add_link_attrs(attrs, new=False):
            attrs[(None, 'target')] = '_blank'
            attrs[(None, 'rel')] = 'noopener noreferrer'
            return attrs

        body_html = bleach.linkify(
            body_html,
            callbacks=[_add_link_attrs],
        )

    return body_html, body_text, attachments

# ============================================================
# W47: квота через IMAP GETQUOTAROOT
# ============================================================

def get_quota(email):
    """
    Возвращает использование и лимит квоты через IMAP GETQUOTAROOT.
    Быстрее, чем `doveadm quota get` (нет sudo, нет повторного Argon2).

    Возвращает (used_bytes, limit_bytes, error):
        - (used, limit, None) — успех.
        - (None, None, 'error message') — ошибка.
    """
    import imaplib

    cfg = current_app.config
    host = cfg.get('MAIL_IMAP_HOST', '127.0.0.1')
    port = cfg.get('MAIL_IMAP_PORT', 143)
    master_user = cfg.get('MAIL_IMAP_MASTER_USER', 'master')
    master_password = cfg.get('MAIL_IMAP_MASTER_PASSWORD', '')

    if not master_password:
        return None, None, 'MAIL_MASTER_PASSWORD не задан'

    login = f'{email}*{master_user}'
    client = None

    try:
        client = imaplib.IMAP4(host, port)
        client.login(login, master_password)
        typ, data = client.getquotaroot('INBOX')

        if typ != 'OK' or not data:
            return None, None, f'GETQUOTAROOT вернул {typ}'

        # Ответ может быть вложенным списком:
        #   [[b'INBOX "User quota"'], [b'"User quota" (STORAGE 3 1048576)']]
        # Рекурсивно разворачиваем до плоского списка строк/байтов.
        import re

        def _flatten(items):
            for item in items:
                if isinstance(item, (list, tuple)):
                    yield from _flatten(item)
                else:
                    yield item

        for item in _flatten(data):
            if not item:
                continue
            if isinstance(item, bytes):
                item = item.decode('utf-8', errors='replace')
            if not isinstance(item, str):
                continue
            m = re.search(r'STORAGE\s+(\d+)\s+(\d+)', item)
            if m:
                usage_kb = int(m.group(1))
                limit_kb = int(m.group(2))
                return usage_kb * 1024, limit_kb * 1024, None

        return None, None, 'STORAGE не найден в ответе'

    except imaplib.IMAP4.error as e:
        logger.warning(f'get_quota IMAP error for {email}: {e}')
        return None, None, f'IMAP: {e}'
    except Exception as e:
        logger.exception(f'get_quota failed for {email}')
        return None, None, f'Ошибка: {e}'
    finally:
        if client:
            try:
                client.logout()
            except Exception:
                pass

# ============================================================
# W47: кэшированное чтение письма
# ============================================================

def get_message_cached(email, folder, uid):
    """
    Обёртка над get_message с кэшем тел (TTL 30 мин).

    Возвращает (message_dict, cached: bool, error).
    При ошибке: (None, False, 'текст ошибки').
    """
    cache_key = f'mail_msg_{email}_{folder}_{uid}'

    cached_msg = cache.get(cache_key)
    if cached_msg is not None:
        return cached_msg, True, None

    msg, err = get_message(email, folder, uid)
    if err:
        return None, False, err

    # Кэшируем на 30 мин
    cache.set(cache_key, msg, timeout=1800)
    return msg, False, None

def append_to_sent(email, raw_message):
    """
    Сохраняет копию письма в папку Sent через IMAP APPEND.
    raw_message — сырые байты письма (MIME).
    Возвращает (ok, error).
    """
    client, err = _make_client(email)
    if err:
        return False, err

    try:
        # Папка Sent (системная папка Dovecot)
        folder = 'Sent'
        # APPEND с флагом \Seen
        client.append(folder, raw_message, flags=[b'\\Seen'])
        return True, None
    except Exception as e:
        logger.exception(f'append_to_sent failed for {email}')
        return False, f'Ошибка APPEND: {e}'
    finally:
        _safe_close(client)

def append_to_drafts(email, raw_message):
    """
    Сохраняет черновик в папку Drafts через IMAP APPEND.
    raw_message — сырые байты письма (MIME).
    Возвращает (ok, error).
    """
    client, err = _make_client(email)
    if err:
        return False, err

    try:
        folder = 'Drafts'
        client.append(folder, raw_message, flags=[b'\\Draft'])
        return True, None
    except Exception as e:
        logger.exception(f'append_to_drafts failed for {email}')
        return False, f'Ошибка APPEND в Drafts: {e}'
    finally:
        _safe_close(client)

def list_sieve_scripts(email):
    """
    Возвращает список Sieve-скриптов из Dovecot (doveadm sieve list).
    Возвращает (scripts_list, error).
    """
    import subprocess
    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')

    try:
        result = subprocess.run(
            ['sudo', doveadm, 'sieve', 'list', '-u', email],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace').strip()
            return None, f'doveadm sieve list: {err}'

        output = result.stdout.decode('utf-8', errors='replace').strip()
        scripts = []
        for line in output.splitlines():
            line = line.strip()
            if line:
                # Dovecot 2.4: "rule_8 ACTIVE" (без скобок)
                upper = line.upper()
                is_active = '(ACTIVE)' in upper or ' ACTIVE' in upper or upper.endswith('ACTIVE')
                # Убираем ACTIVE (с пробелом и без)
                name = line.replace('(active)', '').replace('ACTIVE', '').replace('(ACTIVE)', '').strip().strip('"')
                scripts.append({'name': name, 'is_active': is_active})
        return scripts, None
    except Exception as e:
        logger.exception(f'list_sieve_scripts failed for {email}')
        return None, f'Ошибка: {e}'

def put_sieve_script(email, script_name, script_content):
    """
    Сохраняет Sieve-скрипт в Dovecot (doveadm sieve put).
    Возвращает (ok, error).
    """
    import subprocess
    import tempfile

    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')

    try:
        # Записываем скрипт во временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sieve', delete=False) as f:
            f.write(script_content)
            tmp_path = f.name

        # put (без -a — не активируем, активируем отдельно)
        result = subprocess.run(
            ['sudo', doveadm, 'sieve', 'put', '-u', email, script_name],
            stdin=open(tmp_path, 'rb'),
            capture_output=True,
            timeout=10,
        )
        os.unlink(tmp_path)

        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace').strip()
            return False, f'doveadm sieve put: {err}'

        return True, None
    except Exception as e:
        logger.exception(f'put_sieve_script failed for {email}')
        return False, f'Ошибка: {e}'

def delete_sieve_script(email, script_name):
    """Удаляет Sieve-скрипт (сначала деактивирует, если активен)."""
    import subprocess
    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')
    try:
        # Сначала деактивируем (если активен)
        subprocess.run(
            ['sudo', doveadm, 'sieve', 'deactivate', '-u', email],
            capture_output=True,
            timeout=10,
        )
        # Затем удаляем
        result = subprocess.run(
            ['sudo', doveadm, 'sieve', 'delete', '-u', email, script_name],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0, None if result.returncode == 0 else result.stderr.decode('utf-8', errors='replace')
    except Exception as e:
        logger.exception(f'delete_sieve_script failed')
        return False, str(e)


def activate_sieve_script(email, script_name):
    """Активирует Sieve-скрипт (doveadm sieve activate)."""
    import subprocess
    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')
    try:
        result = subprocess.run(
            ['sudo', doveadm, 'sieve', 'activate', '-u', email, script_name],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0, None if result.returncode == 0 else result.stderr.decode('utf-8', errors='replace')
    except Exception as e:
        logger.exception(f'activate_sieve_script failed')
        return False, str(e)

def search_messages(email, folder, query, limit=50):
    """
    Поиск писем через IMAP SEARCH.
    Ищет по FROM, SUBJECT, BODY.
    Возвращает (results, total, error).
    """
    client, err = _make_client(email)
    if err:
        return None, 0, err

    try:
        client.select_folder(folder, readonly=True)

        # IMAP SEARCH: OR по FROM, SUBJECT, BODY
        # Простой вариант: SEARCH TEXT (ищет везде)
        uids = client.search(['TEXT', query])
        total = len(uids)

        if not uids:
            return [], 0, None

        # Сортируем по убыванию, берём окно
        uids_sorted = sorted(uids, reverse=True)
        window = uids_sorted[:limit]

        fetch_data = client.fetch(window, [
            'FLAGS',
            'BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)]',
            'RFC822.SIZE',
        ])

        results = []
        for uid in window:
            data = fetch_data.get(uid, {})
            raw_headers = data.get(b'BODY[HEADER.FIELDS (FROM SUBJECT DATE)]', b'')
            flags = data.get(b'FLAGS', ())

            headers = _parse_headers(raw_headers)
            from_raw = headers.get('from', '')
            subject = _decode_mime_header(headers.get('subject', ''))
            date_str = headers.get('date', '')
            dt = _parse_date(date_str)

            from_name, from_email = _parse_from(from_raw)

            results.append({
                'uid': uid,
                'subject': subject or '(без темы)',
                'from_name': from_name,
                'from_email': from_email,
                'date': dt,
                'date_human': _human_date(dt),
                'is_read': b'\\Seen' in flags,
                'is_flagged': b'\\Flagged' in flags,
            })

        return results, total, None
    except Exception as e:
        logger.exception(f'search_messages failed for {email}/{folder}')
        return None, 0, f'Ошибка поиска: {e}'
    finally:
        _safe_close(client)

def create_folder(email, name):
    """Создаёт IMAP-папку. Возвращает (ok, error)."""
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.create_folder(name)
        return True, None
    except Exception as e:
        logger.exception(f'create_folder failed for {email}/{name}')
        return False, f'Ошибка создания папки: {e}'
    finally:
        _safe_close(client)


def rename_folder(email, old_name, new_name):
    """Переименовывает IMAP-папку. Возвращает (ok, error)."""
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.rename_folder(old_name, new_name)
        return True, None
    except Exception as e:
        logger.exception(f'rename_folder failed for {email}/{old_name}->{new_name}')
        return False, f'Ошибка переименования: {e}'
    finally:
        _safe_close(client)


def delete_folder(email, name):
    """Удаляет IMAP-папку. Возвращает (ok, error)."""
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.delete_folder(name)
        return True, None
    except Exception as e:
        logger.exception(f'delete_folder failed for {email}/{name}')
        return False, f'Ошибка удаления папки: {e}'
    finally:
        _safe_close(client)

def trash_message(email, folder, uid):
    """
    Перемещает письмо в Trash (IMAP MOVE или COPY+DELETE).
    Возвращает (ok, error).
    """
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.select_folder(folder, readonly=False)

        # Пробуем MOVE (IMAP4rev1 + MOVE extension)
        try:
            client.move([uid], 'Trash')
        except Exception:
            # Fallback: COPY в Trash, затем STORE \Deleted + EXPUNGE
            client.copy([uid], 'Trash')
            client.add_flags([uid], [b'\\Deleted'])
            client.expunge()

        return True, None
    except Exception as e:
        logger.exception(f'trash_message failed for {email}/{folder}/{uid}')
        return False, f'Ошибка удаления: {e}'
    finally:
        _safe_close(client)

def delete_message(email, folder, uid):
    """
    Удаляет письмо окончательно (STORE \Deleted + EXPUNGE).
    Возвращает (ok, error).
    """
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.select_folder(folder, readonly=False)
        client.add_flags([uid], [b'\\Deleted'])
        client.expunge()
        return True, None
    except Exception as e:
        logger.exception(f'delete_message failed for {email}/{folder}/{uid}')
        return False, f'Ошибка удаления: {e}'
    finally:
        _safe_close(client)

def move_message(email, folder, uid, dest_folder):
    """
    Перемещает письмо из folder в dest_folder (IMAP MOVE или COPY+DELETE).
    Возвращает (ok, error).
    """
    client, err = _make_client(email)
    if err:
        return False, err
    try:
        client.select_folder(folder, readonly=False)
        # Пробуем MOVE
        try:
            client.move([uid], dest_folder)
        except Exception:
            # Fallback: COPY + DELETE
            client.copy([uid], dest_folder)
            client.add_flags([uid], [b'\\Deleted'])
            client.expunge()
        return True, None
    except Exception as e:
        logger.exception(f'move_message failed for {email}/{folder}/{uid}->{dest_folder}')
        return False, f'Ошибка перемещения: {e}'
    finally:
        _safe_close(client)