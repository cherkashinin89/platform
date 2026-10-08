# slug_utils.py - Утилиты для генерации slug
#
# Поддерживает:
#   - кириллицу
#   - автогенерацию из заголовка
#   - уникализацию (добавляет -2, -3, ...)
import re


def slugify(text, allow_cyrillic=True):
    """
    Преобразует текст в slug.

    Примеры:
        "Мои контакты" → "мои-контакты"
        "About Us 2026" → "about-us-2026"
        "Статья №1" → "статья-1"
    """
    if not text:
        return ''

    # Нижний регистр
    text = text.strip().lower()

    if allow_cyrillic:
        # Оставляем: буквы (в т.ч. кириллица), цифры, пробелы, дефисы
        text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
        # Пробелы и подчёркивания → дефисы
        text = re.sub(r'[\s_]+', '-', text)
        # Множественные дефисы → один
        text = re.sub(r'-+', '-', text)
        # Убираем дефисы по краям
        text = text.strip('-')
    else:
        # Транслит в латиницу
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        result = []
        for char in text:
            if char in translit_map:
                result.append(translit_map[char])
            elif char.isalnum() or char in ' -_':
                result.append(char)
        text = ''.join(result)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text)
        text = text.strip('-')

    return text


def unique_slug(model, base_slug, exclude_id=None):
    """
    Делает slug уникальным:
    если такой уже есть в БД — добавляет -2, -3, ...

    Параметры:
        model — SQLAlchemy-модель (Page, Article, Album)
        base_slug — базовый slug
        exclude_id — ID, который исключить из проверки (при редактировании)
    """
    if not base_slug:
        return ''

    slug = base_slug
    counter = 1

    while True:
        query = model.query.filter_by(slug=slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if not query.first():
            return slug
        counter += 1
        slug = f'{base_slug}-{counter}'