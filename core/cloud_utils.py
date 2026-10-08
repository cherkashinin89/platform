# cloud_utils.py - утилиты доступа к облачным файлам
#
# myframework и mycloud работают с одной БД (cloud_file).
# Этот модуль — единственная точка чтения облачных файлов из myframework.
# Запись (загрузка/удаление) — по-прежнему в mycloud.
import os
from flask import current_app


def cloud_data_root():
    """Корень физического хранилища облака (общий для myframework и mycloud)."""
    # Договорённость: cloud_data лежит рядом с mycloud, но читать может и myframework
    # (процессы под одним юзером deploy).
    # Путь берём из конфига, если задан, иначе — из окружения, иначе — хардкод.
    path = current_app.config.get('CLOUD_DATA_ROOT')
    if path:
        return path
    # Фолбэк: соседний проект. Позже вынесем в .env
    return os.path.expanduser('~/apps/mycloud/cloud_data')


def get_cloud_path(file):
    """
    Возвращает физический путь к файлу CloudFile.
    Для папки вернёт путь к папке.
    """
    if not file or not file.stored_name:
        return None
    return os.path.join(cloud_data_root(), str(file.owner_id), file.stored_name)


def list_cloud_files(owner_id, parent_id=None, file_type=None,
                     query=None, include_trashed=False, only_folders=False):
    """
    Возвращает список CloudFile владельца.

    :param owner_id: id пользователя
    :param parent_id: id родительской папки (None = корень)
    :param file_type: 'image' / 'document' / ... (по mime) или None
    :param query: поиск по name (подстрока)
    :param include_trashed: включить корзину
    :param only_folders: только папки
    """
    from models import CloudFile
    q = CloudFile.query.filter_by(owner_id=owner_id)
    if not include_trashed:
        q = q.filter_by(is_trashed=False)
    if parent_id is None:
        q = q.filter(CloudFile.parent_id.is_(None))
    else:
        q = q.filter_by(parent_id=parent_id)
    if only_folders:
        q = q.filter_by(is_folder=True)
    if query:
        q = q.filter(CloudFile.name.ilike(f'%{query}%'))
    files = q.order_by(CloudFile.is_folder.desc(), CloudFile.name).all()
    if file_type:
        files = [f for f in files if f.is_folder or _matches_type(f, file_type)]
    return files


def _matches_type(file, file_type):
    """Проверяет, относится ли файл к категории (image/document/...)."""
    mime = (file.mime_type or '').lower()
    if file_type == 'image':
        return mime.startswith('image/')
    if file_type == 'video':
        return mime.startswith('video/')
    if file_type == 'audio':
        return mime.startswith('audio/')
    if file_type == 'document':
        return any(x in mime for x in (
            'pdf', 'word', 'excel', 'powerpoint', 'text', 'officedocument',
        ))
    if file_type == 'archive':
        return any(x in mime for x in ('zip', 'tar', 'gzip', 'rar', '7z'))
    return True


def get_cloud_file(file_id, owner_id=None):
    """
    Возвращает CloudFile по id.
    Если owner_id задан — проверяет принадлежность.
    """
    from models import CloudFile
    f = CloudFile.query.get(file_id)
    if not f:
        return None
    if owner_id is not None and f.owner_id != owner_id:
        return None
    return f


def user_used_bytes(owner_id):
    """Занятое место пользователя (включая корзину)."""
    from models import CloudFile, db
    total = (
        db.session.query(db.func.coalesce(db.func.sum(CloudFile.size), 0))
        .filter(CloudFile.owner_id == owner_id)
        .filter(CloudFile.is_folder.is_(False))
        .scalar()
    )
    return int(total or 0)


def media_url(file_id):
    """Публичный URL файла для вставки в HTML."""
    return f'/media/{file_id}'


def cloud_file_by_stored_name(stored_name):
    """Обратный поиск: по stored_name найти CloudFile (для отдачи через /media)."""
    from models import CloudFile
    if not stored_name:
        return None
    return CloudFile.query.filter_by(stored_name=stored_name).first()