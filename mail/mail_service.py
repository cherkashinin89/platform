# mail/mail_service.py — обёртки над doveadm/systemctl
import os
import shutil
import subprocess
import logging
from flask import current_app
from datetime import datetime

logger = logging.getLogger(__name__)


def _run(cmd, timeout=None, input_data=None):
    """
    Запускает команду, возвращает (ok, stdout, stderr).
    """
    if timeout is None:
        timeout = current_app.config.get('SUBPROCESS_TIMEOUT', 10)

    try:
        result = subprocess.run(
            cmd,
            input=input_data.encode() if input_data else None,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout.decode('utf-8', errors='replace').strip()
        stderr = result.stderr.decode('utf-8', errors='replace').strip()
        ok = result.returncode == 0
        if not ok:
            logger.warning(f'Команда {cmd} вернула {result.returncode}: {stderr}')
        return ok, stdout, stderr
    except subprocess.TimeoutExpired:
        logger.error(f'Таймаут команды {cmd}')
        return False, '', 'timeout'
    except Exception as e:
        logger.exception(f'Ошибка запуска {cmd}')
        return False, '', str(e)


def hash_password(password):
    """
    Генерирует хэш пароля в формате Dovecot (SHA512-CRYPT).
    Возвращает (ok, hash_or_error).
    """
    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')
    ok, stdout, stderr = _run([doveadm, 'pw', '-s', 'SHA512-CRYPT', '-p', password])
    if not ok:
        return False, stderr or 'doveadm pw failed'
    return True, stdout.strip()


def get_quota(email):
    """
    Возвращает использование квоты ящика.
    doveadm quota get требует root — идём через sudo.
    Limit возвращается в KB, конвертируем в байты.
    """
    doveadm = current_app.config.get('DOVEADM', '/usr/bin/doveadm')
    ok, stdout, stderr = _run(['sudo', doveadm, 'quota', 'get', '-u', email])
    if not ok:
        return False, stderr or 'doveadm quota get failed'

    used_bytes = 0
    quota_bytes = 0
    for line in stdout.splitlines():
        parts = line.split()
        # Строка данных: ['User', 'quota', 'STORAGE', '<used_kb>', '<limit_kb>', '<percent>']
        if len(parts) >= 5 and parts[0] == 'User' and parts[2] == 'STORAGE':
            try:
                used_kb = int(parts[3])
                limit_kb = int(parts[4]) if parts[4] != '-' else 0
                used_bytes = used_kb * 1024
                quota_bytes = limit_kb * 1024
            except (ValueError, IndexError):
                pass
            break

    return True, {'used_bytes': used_bytes, 'quota_bytes': quota_bytes}


def reload_service(service):
    """
    Перезагружает указанный сервис через sudo systemctl reload.
    service ∈ {'postfix', 'dovecot', 'rspamd'}.
    Возвращает (ok, error).
    """
    allowed = current_app.config.get('ALLOWED_SYSTEMCTL', ['postfix', 'dovecot', 'rspamd'])
    if service not in allowed:
        return False, f'Сервис {service} не разрешён'

    systemctl = current_app.config.get('SYSTEMCTL', '/usr/bin/systemctl')
    ok, stdout, stderr = _run(['sudo', systemctl, 'reload', service])
    if not ok:
        return False, stderr or f'reload {service} failed'
    return True, None

def archive_mailbox(email):
    """
    Архивирует Maildir ящика в /tmp/<email>_<YYYYMMDD_HHMMSS>.tar.gz.
    Возвращает (ok, archive_path | None | error).

    Если директория ящика не существует (писем не было) — (True, None).
    Файл во временной директории принадлежит deploy — framework его переместит.
    """
    if '@' not in email:
        return False, 'Некорректный email'

    local_part, domain = email.split('@', 1)
    vmail_home = current_app.config.get('VMAIL_HOME', '/var/vmail')

    mailbox_dir = os.path.join(vmail_home, domain, local_part)

    # Проверяем существование через sudo (deploy не видит /var/vmail/)
    ok, _, _ = _run(['sudo', '/bin/ls', '-d', mailbox_dir])
    if not ok:
        # Директории нет — ящик пустой, архивировать нечего
        return True, None

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    archive_name = f'{email}_{timestamp}.tar.gz'
    archive_path = os.path.join('/tmp', archive_name)

    # Архивируем в /tmp
    ok, _, err = _run([
        'sudo', '/bin/tar', '-czf', archive_path,
        '-C', os.path.join(vmail_home, domain),
        local_part,
    ], timeout=120)
    if not ok:
        return False, f'Не удалось заархивировать: {err}'

    # Смена владельца — чтобы deploy мог переместить
    ok, _, err = _run(['sudo', '/bin/chown', 'deploy:deploy', archive_path])
    if not ok:
        return False, f'Не удалось сменить владельца архива: {err}'

    return True, archive_path    

def create_maildir(email):
    """
    Создаёт Maildir для ящика (если ещё нет).
    Структура: <VMAIL_HOME>/<domain>/<local_part>/{cur,new,tmp}
    Возвращает (ok, error).
    """
    if '@' not in email:
        return False, 'Некорректный email'

    local_part, domain = email.split('@', 1)
    vmail_home = current_app.config.get('VMAIL_HOME', '/var/vmail')

    domain_dir = os.path.join(vmail_home, domain)
    mailbox_dir = os.path.join(domain_dir, local_part)

    # Создаём domain dir (если нет)
    ok, _, err = _run(['sudo', '/bin/mkdir', '-p', domain_dir])
    if not ok:
        return False, f'Не удалось создать {domain_dir}: {err}'

    # Создаём mailbox dir с подпапками
    ok, _, err = _run(['sudo', '/bin/mkdir', '-p',
                       os.path.join(mailbox_dir, 'cur'),
                       os.path.join(mailbox_dir, 'new'),
                       os.path.join(mailbox_dir, 'tmp')])
    if not ok:
        return False, f'Не удалось создать Maildir: {err}'

    # Права vmail:vmail 0700
    ok, _, err = _run(['sudo', '/bin/chown', '-R', 'vmail:vmail', mailbox_dir])
    if not ok:
        return False, f'Не удалось сменить владельца: {err}'

    ok, _, err = _run(['sudo', '/bin/chmod', '-R', '0700', mailbox_dir])
    if not ok:
        return False, f'Не удалось сменить права: {err}'

    return True, None

def send_mail(from_addr, to_addrs, subject, body_html, body_text=None,
              cc_addrs=None, bcc_addrs=None, attachments=None):
    """
    Отправляет письмо через локальный sendmail (Postfix).
    attachments — список кортежей (filename, content_type, data_bytes).
    Возвращает (ok, error, raw_message).
    """
    import email.message
    import email.utils
    import re
    from email.mime.base import MIMEBase
    from email import encoders

    if not body_html:
        body_html = '<p></p>'

    msg = email.message.EmailMessage()
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)
    if cc_addrs:
        msg['Cc'] = ', '.join(cc_addrs)
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = email.utils.make_msgid(domain=from_addr.split('@')[-1])

    plain = body_text if body_text else re.sub(r'<[^>]+>', '', body_html)
    msg.set_content(plain)
    msg.add_alternative(body_html, subtype='html')

    # Вложения
    if attachments:
        for fname, ctype, data in attachments:
            maintype, _, subtype = ctype.partition('/')
            if not subtype:
                maintype, subtype = 'application', 'octet-stream'
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=('utf-8', '', fname),
            )
            msg.attach(part)

    sendmail_path = current_app.config.get('SENDMAIL', '/usr/sbin/sendmail')
    try:
        result = subprocess.run(
            [sendmail_path, '-f', from_addr, '-t'],
            input=msg.as_bytes(),
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')
            logger.error(f'sendmail failed: {err}')
            return False, f'sendmail: {err}', None
        return True, None, msg.as_bytes()
    except Exception as e:
        logger.exception('send_mail failed')
        return False, f'Ошибка отправки: {e}', None