# image_utils.py — генерация миниатюр для загруженных изображений
import os
from PIL import Image

# === Настройки ===
# Максимальный размер миниатюры (ширина × высота).
# Пропорции сохраняются: картинка «вписывается» в этот прямоугольник.
THUMBNAIL_SIZE = (700, 500)

# Качество JPEG (0–100). 80 — хороший баланс размера и качества.
THUMBNAIL_QUALITY = 80

# Префикс имени файла-миниатюры.
THUMBNAIL_PREFIX = 'thumb_'

# Расширения, для которых имеет смысл делать миниатюру.
THUMBNAIL_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif', 'tiff', 'tif'}


def can_thumbnail(filename):
    """
    Проверяет, можно ли сделать миниатюру для файла по его имени.
    Возвращает True/False.
    """
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in THUMBNAIL_EXTENSIONS


def thumbnail_name_for(original_name):
    """
    Возвращает имя файла-миниатюры для оригинального имени.
    Например: '20260919_abc.jpg' → 'thumb_20260919_abc.jpg'.
    """
    return THUMBNAIL_PREFIX + original_name


def create_thumbnail(source_path, dest_path,
                     size=THUMBNAIL_SIZE, quality=THUMBNAIL_QUALITY):
    """
    Создаёт уменьшенную копию изображения.

    :param source_path: путь к оригиналу
    :param dest_path: куда сохранить миниатюру
    :param size: кортеж (макс_ширина, макс_высота)
    :param quality: качество JPEG (0–100)
    :return: True если успешно, False если нет
    """
    try:
        with Image.open(source_path) as img:
            # === Приведение к RGB ===
            # PNG/GIF с прозрачностью нужно «посадить» на белый фон,
            # иначе при сохранении в JPEG прозрачность станет чёрной.
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode == 'P':
                # Палитровые (GIF) — конвертируем в RGBA, потом на белый фон
                img = img.convert('RGBA')
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # === Уменьшение с сохранением пропорций ===
            img.thumbnail(size, Image.LANCZOS)

            # === Сохранение как JPEG ===
            img.save(dest_path, 'JPEG', quality=quality, optimize=True)

        return True
    except Exception as e:
        # Логируем ошибку, но не «роняем» приложение
        print(f'[image_utils] Ошибка создания миниатюры {source_path}: {e}')
        return False
