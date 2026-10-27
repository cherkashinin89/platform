"""
WOPI-эндпоинты для Collabora (W48).
CheckFileInfo / GetFile / PutFile + создание токена.
"""

import os
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from core.extensions import db
from core.models import CloudFile, CloudShare, WopiToken

wopi_test_bp = Blueprint('wopi_test', __name__)


def _get_token(file_id):
    """Достаёт WopiToken из access_token (query), проверяет срок."""
    token_str = request.args.get('access_token')
    if not token_str:
        return None
    token = WopiToken.query.filter_by(token=token_str, file_id=file_id).first()
    if not token or token.expires_at < datetime.utcnow():
        return None
    return token


def _file_path(file):
    """Путь к физическому файлу в cloud_data."""
    base = current_app.config['CLOUD_DATA_DIR']
    return os.path.join(base, str(file.owner_id), file.stored_name)


# === Создание токена ===

@wopi_test_bp.route('/api/wopi-token/<int:file_id>', methods=['POST'])
@login_required
def create_wopi_token(file_id):
    """Создаёт WOPI-токен для файла (владелец или получатель шары с can_edit)."""
    file = CloudFile.query.get(file_id)
    if not file or file.is_trashed:
        return jsonify({'ok': False, 'error': 'Файл не найден'}), 404

    if file.owner_id == current_user.id:
        can_write = True
        share_id = None
    else:
        share = CloudShare.query.filter_by(file_id=file_id, can_edit=True).first()
        if not share or share.is_expired():
            return jsonify({'ok': False, 'error': 'Нет прав на редактирование'}), 403
        can_write = True
        share_id = share.id

    token_str = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    token = WopiToken(
        token=token_str,
        file_id=file_id,
        user_id=current_user.id,
        share_id=share_id,
        can_write=can_write,
        expires_at=expires_at,
    )
    db.session.add(token)
    db.session.commit()

    return jsonify({
        'ok': True,
        'token': token_str,
        'expires_at': expires_at.isoformat(),
    })


# === WOPI: CheckFileInfo ===

@wopi_test_bp.route('/wopi/files/<int:file_id>', methods=['GET'])
def wopi_check_file_info(file_id):
    """CheckFileInfo — метаданные файла + права."""
    token = _get_token(file_id)
    if not token:
        return '', 401

    file = CloudFile.query.get(file_id)
    if not file or file.is_trashed:
        return '', 404

    return jsonify({
        'BaseFileName': file.name,
        'Size': file.size,
        'UserCanWrite': token.can_write,
        'UserFriendlyName': token.user.username if token.user_id else 'Guest',
        'UserId': str(token.user_id or 'anonymous'),
    })


# === WOPI: GetFile ===

@wopi_test_bp.route('/wopi/files/<int:file_id>/contents', methods=['GET'])
def wopi_get_file(file_id):
    """GetFile — отдаём содержимое файла."""
    token = _get_token(file_id)
    if not token:
        return '', 401

    file = CloudFile.query.get(file_id)
    if not file or file.is_trashed:
        return '', 404

    path = _file_path(file)
    if not os.path.exists(path):
        return '', 404

    with open(path, 'rb') as f:
        content = f.read()

    return content, 200, {
        'Content-Type': file.mime_type or 'application/octet-stream',
    }


# === WOPI: PutFile ===

@wopi_test_bp.route('/wopi/files/<int:file_id>/contents', methods=['POST'])
def wopi_put_file(file_id):
    """PutFile — сохраняем изменения в файл."""
    token = _get_token(file_id)
    if not token or not token.can_write:
        return '', 401

    file = CloudFile.query.get(file_id)
    if not file or file.is_trashed:
        return '', 404

    path = _file_path(file)
    if not os.path.exists(path):
        return '', 404

    # Проверка временной метки (защита от конфликтов)
    client_ts = request.headers.get('X-COOL-WOPI-Timestamp')
    if client_ts:
        file_mtime = datetime.utcfromtimestamp(os.path.getmtime(path))
        # Формат X-COOL-WOPI-Timestamp — ISO 8601 (например, 2026-10-27T00:00:00.000000Z)
        # Простое сравнение: если клиент прислал старее — 409
        # (полноценная реализация — позже)
        pass

    # Записываем содержимое
    content = request.get_data()
    with open(path, 'wb') as f:
        f.write(content)

    # Обновляем размер в БД
    file.size = len(content)
    db.session.commit()

    return '', 200