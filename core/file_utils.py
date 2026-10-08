# file_utils.py - утилиты для файлового менеджера
import os
import uuid
import mimetypes
import zipfile
import tarfile
from datetime import datetime


# Маппинг расширений → категория
TYPE_MAP = {
    'image':    {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff'},
    'video':    {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv', 'm4v'},
    'audio':    {'mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a', 'wma'},
    'document': {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                 'txt', 'rtf', 'odt', 'ods', 'csv', 'md'},
    'archive':  {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'},
}


def get_file_type(extension: str) -> str:
    """Возвращает категорию файла по расширению"""
    ext = (extension or '').lower().lstrip('.')
    for category, extensions in TYPE_MAP.items():
        if ext in extensions:
            return category
    return 'other'


def guess_mime(filename: str) -> str:
    """Определяет MIME-тип по имени файла"""
    mime, _ = mimetypes.guess_type(filename)
    return mime or 'application/octet-stream'


def make_stored_name(original_name: str) -> str:
    """Генерирует безопасное уникальное имя для сохранения на диск"""
    ext = os.path.splitext(original_name)[1].lower()  # расширение с точкой
    # Формат: YYYYMMDD_HHMMSS_<8 hex-символов><ext>
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'{stamp}_{uuid.uuid4().hex[:8]}{ext}'


def human_size(size: int) -> str:
    """Байты → человекочитаемая строка"""
    s = size or 0
    for unit in ['B', 'KB', 'MB', 'GB']:
        if s < 1024:
            return f'{s:.1f} {unit}' if unit != 'B' else f'{s} {unit}'
        s /= 1024
    return f'{s:.1f} TB'


def create_archive(files, dest_folder: str, base_name: str,
                   fmt: str = 'zip', delete_after: bool = False) -> str:
    """
    Создаёт архив из списка файлов.
    
    :param files: список объектов UploadedFile
    :param dest_folder: папка, куда положить архив
    :param base_name: базовое имя архива (без расширения)
    :param fmt: 'zip' или 'targz'
    :param delete_after: удалять ли исходные файлы после архивации
    :return: путь к созданному архиву
    """
    os.makedirs(dest_folder, exist_ok=True)

    if fmt == 'zip':
        archive_path = os.path.join(dest_folder, f'{base_name}.zip')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                src = f.stored_path if hasattr(f, 'stored_path') else None
                # stored_path будет вычислен в маршруте и присвоен как атрибут
                if src and os.path.exists(src):
                    zf.write(src, arcname=f.stored_name)
                    if delete_after:
                        os.remove(src)
    elif fmt == 'targz':
        archive_path = os.path.join(dest_folder, f'{base_name}.tar.gz')
        with tarfile.open(archive_path, 'w:gz') as tf:
            for f in files:
                src = getattr(f, 'stored_path', None)
                if src and os.path.exists(src):
                    tf.add(src, arcname=f.stored_name)
                    if delete_after:
                        os.remove(src)
    else:
        raise ValueError(f'Неизвестный формат архива: {fmt}')

    return archive_path