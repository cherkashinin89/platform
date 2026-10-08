# core/files_icons.py - Иконки файлов и форматирование размеров
#
# Общие утилиты для отображения файлов в UI.
# Используются в framework (модалка TinyMCE, файловый менеджер)
# и в cloud (проводник, корзина, шары).
from flask import current_app


def format_bytes(num):
    """Человекочитаемый размер: 1.5 МБ, 340 КБ и т.д."""
    if num is None:
        return '—'
    num = int(num)
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if num < 1024:
            return f'{num} {unit}' if unit == 'Б' else f'{num:.1f} {unit}'
        num /= 1024
    return f'{num:.1f} ПБ'


# Точные расширения → (иконка Bootstrap Icons, цвет CSS)
_ICON_BY_EXT = {
    # PDF
    'pdf': ('bi-file-earmark-pdf', '#dc3545'),

    # Word
    'doc':  ('bi-file-earmark-word', '#0d6efd'),
    'docx': ('bi-file-earmark-word', '#0d6efd'),
    'rtf':  ('bi-file-earmark-word', '#0d6efd'),
    'odt':  ('bi-file-earmark-word', '#0d6efd'),

    # Excel
    'xls':  ('bi-file-earmark-excel', '#198754'),
    'xlsx': ('bi-file-earmark-excel', '#198754'),
    'csv':  ('bi-file-earmark-excel', '#198754'),
    'ods':  ('bi-file-earmark-excel', '#198754'),

    # PowerPoint
    'ppt':  ('bi-file-earmark-ppt', '#fd7e14'),
    'pptx': ('bi-file-earmark-ppt', '#fd7e14'),
    'odp':  ('bi-file-earmark-ppt', '#fd7e14'),

    # Текст
    'txt': ('bi-file-earmark-text', '#6c757d'),
    'md':  ('bi-file-earmark-text', '#6c757d'),

    # Архивы
    'zip': ('bi-file-earmark-zip', '#6f42c1'),
    'rar': ('bi-file-earmark-zip', '#6f42c1'),
    '7z':  ('bi-file-earmark-zip', '#6f42c1'),
    'tar': ('bi-file-earmark-zip', '#6f42c1'),
    'gz':  ('bi-file-earmark-zip', '#6f42c1'),
    'bz2': ('bi-file-earmark-zip', '#6f42c1'),

    # Изображения
    'jpg':  ('bi-file-earmark-image', '#0dcaf0'),
    'jpeg': ('bi-file-earmark-image', '#0dcaf0'),
    'png':  ('bi-file-earmark-image', '#0dcaf0'),
    'gif':  ('bi-file-earmark-image', '#0dcaf0'),
    'webp': ('bi-file-earmark-image', '#0dcaf0'),
    'svg':  ('bi-file-earmark-image', '#0dcaf0'),
    'bmp':  ('bi-file-earmark-image', '#0dcaf0'),
    'ico':  ('bi-file-earmark-image', '#0dcaf0'),

    # Видео
    'mp4':  ('bi-file-earmark-play', '#dc3545'),
    'avi':  ('bi-file-earmark-play', '#dc3545'),
    'mkv':  ('bi-file-earmark-play', '#dc3545'),
    'mov':  ('bi-file-earmark-play', '#dc3545'),
    'webm': ('bi-file-earmark-play', '#dc3545'),
    'wmv':  ('bi-file-earmark-play', '#dc3545'),

    # Аудио
    'mp3':  ('bi-file-earmark-music', '#20c997'),
    'wav':  ('bi-file-earmark-music', '#20c997'),
    'ogg':  ('bi-file-earmark-music', '#20c997'),
    'flac': ('bi-file-earmark-music', '#20c997'),
    'm4a':  ('bi-file-earmark-music', '#20c997'),
    'aac':  ('bi-file-earmark-music', '#20c997'),

    # Код
    'py':   ('bi-file-earmark-code', '#0f172a'),
    'js':   ('bi-file-earmark-code', '#0f172a'),
    'css':  ('bi-file-earmark-code', '#0f172a'),
    'html': ('bi-file-earmark-code', '#0f172a'),
    'json': ('bi-file-earmark-code', '#0f172a'),
    'xml':  ('bi-file-earmark-code', '#0f172a'),
    'php':  ('bi-file-earmark-code', '#0f172a'),
    'rb':   ('bi-file-earmark-code', '#0f172a'),
    'go':   ('bi-file-earmark-code', '#0f172a'),
    'rs':   ('bi-file-earmark-code', '#0f172a'),
    'java': ('bi-file-earmark-code', '#0f172a'),
}

# Fallback по категории (file_type)
_ICON_BY_TYPE = {
    'video':    ('bi-file-earmark-play', '#dc3545'),
    'audio':    ('bi-file-earmark-music', '#20c997'),
    'archive':  ('bi-file-earmark-zip', '#6f42c1'),
    'document': ('bi-file-earmark-text', '#6c757d'),
    'image':    ('bi-file-earmark-image', '#0dcaf0'),
    'other':    ('bi-file-earmark', '#6c757d'),
}


def icon_for_file(name, file_type=None):
    """
    Возвращает (css_class, color) для иконки файла.
    Пример: icon_for_file('отчёт.pdf') → ('bi-file-earmark-pdf', '#dc3545')
    """
    if not name:
        return ('bi-file-earmark', '#6c757d')

    ext = ''
    if '.' in name:
        ext = name.rsplit('.', 1)[-1].lower()

    if ext in _ICON_BY_EXT:
        return _ICON_BY_EXT[ext]

    if file_type in _ICON_BY_TYPE:
        return _ICON_BY_TYPE[file_type]

    return ('bi-file-earmark', '#6c757d')


def icon_for_folder():
    """Возвращает (css_class, color) для папки."""
    return ('bi-folder-fill', 'var(--color-primary)')