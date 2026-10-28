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

wopi_bp = Blueprint('wopi', __name__)


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

@wopi_bp.route('/api/wopi-token/<int:file_id>', methods=['POST'])
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

@wopi_bp.route('/wopi/files/<int:file_id>', methods=['GET'])
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

@wopi_bp.route('/wopi/files/<int:file_id>/contents', methods=['GET'])
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

@wopi_bp.route('/wopi/files/<int:file_id>/contents', methods=['POST'])
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

    # Сохраняем старую версию (история)
    if os.path.exists(path):
        import uuid
        from core.models import CloudFileVersion

        versions_dir = os.path.join(
            current_app.config['CLOUD_DATA_DIR'],
            str(file.owner_id), '.versions', str(file.id)
        )
        os.makedirs(versions_dir, exist_ok=True)

        # Имя версии: uuid + расширение оригинала
        ext = os.path.splitext(file.stored_name)[1] if file.stored_name else ''
        version_name = uuid.uuid4().hex + ext
        version_path = os.path.join(versions_dir, version_name)

        import shutil
        shutil.copy2(path, version_path)

        db.session.add(CloudFileVersion(
            file_id=file.id,
            stored_name=version_name,
            size=os.path.getsize(version_path),
            created_by_id=token.user_id,
        ))
        db.session.flush()

    # Записываем содержимое
    content = request.get_data()
    with open(path, 'wb') as f:
        f.write(content)

    # Обновляем размер в БД
    file.size = len(content)
    db.session.commit()

    return '', 200

@wopi_bp.route('/api/versions/<int:file_id>', methods=['GET'])
@login_required
def list_versions(file_id):
    """Список версий файла (история)."""
    file = CloudFile.query.get(file_id)
    if not file or file.owner_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Нет доступа'}), 403

    from core.models import CloudFileVersion
    versions = CloudFileVersion.query.filter_by(file_id=file_id).order_by(
        CloudFileVersion.created_at.desc()
    ).all()

    return jsonify({
        'ok': True,
        'versions': [{
            'id': v.id,
            'size': v.size,
            'created_at': v.created_at.isoformat(),
            'created_by': v.created_by.username if v.created_by else None,
        } for v in versions],
    })

@wopi_bp.route('/api/versions/<int:file_id>/restore/<int:version_id>', methods=['POST'])
@login_required
def restore_version(file_id, version_id):
    """Откат к указанной версии (с сохранением текущей как новой версии)."""
    import shutil
    import uuid

    from core.models import CloudFileVersion

    file = CloudFile.query.get(file_id)
    if not file or file.owner_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Нет доступа'}), 403

    version = CloudFileVersion.query.filter_by(id=version_id, file_id=file_id).first()
    if not version:
        return jsonify({'ok': False, 'error': 'Версия не найдена'}), 404

    base = current_app.config['CLOUD_DATA_DIR']
    file_path = os.path.join(base, str(file.owner_id), file.stored_name)
    versions_dir = os.path.join(base, str(file.owner_id), '.versions', str(file.id))
    version_path = os.path.join(versions_dir, version.stored_name)

    if not os.path.exists(version_path):
        return jsonify({'ok': False, 'error': 'Файл версии не найден'}), 404

    # Сохраняем текущее состояние как новую версию (перед откатом)
    if os.path.exists(file_path):
        ext = os.path.splitext(file.stored_name)[1] if file.stored_name else ''
        backup_name = uuid.uuid4().hex + ext
        backup_path = os.path.join(versions_dir, backup_name)
        os.makedirs(versions_dir, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        db.session.add(CloudFileVersion(
            file_id=file.id,
            stored_name=backup_name,
            size=os.path.getsize(backup_path),
            created_by_id=current_user.id,
        ))

    # Восстанавливаем выбранную версию как основной файл
    shutil.copy2(version_path, file_path)
    file.size = os.path.getsize(file_path)
    db.session.commit()

    return jsonify({'ok': True})

@wopi_bp.route('/api/collabora-status', methods=['GET'])
def collabora_status():
    """Проверка доступности Collabora (для JS)."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen('http://127.0.0.1:9980/hosting/discovery', timeout=2) as r:
            return jsonify({'ok': r.status == 200})
    except Exception:
        return jsonify({'ok': False})