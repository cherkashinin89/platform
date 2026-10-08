# cloud_service.py - Сервисный слой облачного хранилища
#
# Здесь собраны функции для работы с CloudFile:
# - список файлов в папке
# - расчёт занятого/свободного места
# - проверки прав доступа
#
# Маршруты (app.py) вызывают функции отсюда.
import os
import uuid
import mimetypes
import secrets
from flask import current_app
from datetime import datetime
from sqlalchemy import func

from extensions import db
from models import CloudFile, CloudShare, User



# =============================================================
# СПИСКИ ФАЙЛОВ
# =============================================================

def list_folder(owner_id, parent_id=None, include_trashed=False):
    """
    Возвращает список CloudFile внутри папки parent_id.
    parent_id=None → корень пользователя.

    Сортировка: сначала папки, потом файлы; внутри каждой группы — по имени.
    """
    query = CloudFile.query.filter_by(owner_id=owner_id, parent_id=parent_id)

    if not include_trashed:
        query = query.filter_by(is_trashed=False)

    # Папки — вперёд. Для этого сортируем по is_folder (desc), потом по name.
    return query.order_by(
        CloudFile.is_folder.desc(),
        func.lower(CloudFile.name).asc(),
    ).all()

def get_all_folders(owner_id):
    """
    Возвращает ВСЕ папки пользователя (не в корзине) в виде плоского списка.

    Каждый элемент — dict с полями id, name, parent_id.
    Используется для построения дерева на фронтенде.
    """
    folders = (
        CloudFile.query
        .filter_by(
            owner_id=owner_id,
            is_folder=True,
            is_trashed=False,
        )
        .order_by(CloudFile.name.asc())
        .all()
    )

    return [
        {
            'id': f.id,
            'name': f.name,
            'parent_id': f.parent_id,
        }
        for f in folders
    ]


def get_folder(owner_id, folder_id):
    """
    Возвращает папку по ID, если она принадлежит пользователю и не в корзине.
    Иначе — None.

    Безопасность: проверяем owner_id, чтобы нельзя было получить чужую папку.
    """
    if folder_id is None:
        return None   # корень — не объект

    return CloudFile.query.filter_by(
        id=folder_id,
        owner_id=owner_id,
        is_folder=True,
        is_trashed=False,
    ).first()


def get_file(owner_id, file_id, allow_trashed=False):
    """
    Возвращает файл (не папку) по ID, если он принадлежит пользователю.
    """
    query = CloudFile.query.filter_by(
        id=file_id,
        owner_id=owner_id,
        is_folder=False,
    )

    if not allow_trashed:
        query = query.filter_by(is_trashed=False)

    return query.first()


def get_item(owner_id, item_id, allow_trashed=False):
    """
    Возвращает любой элемент (файл или папку) по ID, если он принадлежит пользователю.
    """
    query = CloudFile.query.filter_by(
        id=item_id,
        owner_id=owner_id,
    )

    if not allow_trashed:
        query = query.filter_by(is_trashed=False)

    return query.first()

# =============================================================
# СОЗДАНИЕ / ИЗМЕНЕНИЕ
# =============================================================

# Запрещённые символы в имени файла/папки
FORBIDDEN_CHARS = set('/\\:*?"<>|')


def validate_name(name):
    """
    Проверяет имя файла/папки.
    Возвращает (ok: bool, error: str|None).
    """
    if name is None:
        return False, 'Имя не задано'

    name = name.strip()
    if not name:
        return False, 'Имя не может быть пустым'

    if len(name) > 255:
        return False, 'Имя слишком длинное (максимум 255 символов)'

    if name in ('.', '..'):
        return False, 'Недопустимое имя'

    if any(c in FORBIDDEN_CHARS for c in name):
        return False, 'Имя содержит недопустимые символы: / \\ : * ? " < > |'

    # Управляющие символы (кроме таба)
    if any(ord(c) < 32 for c in name):
        return False, 'Имя содержит управляющие символы'

    return True, None


def name_exists(owner_id, parent_id, name, exclude_id=None):
    """
    Проверяет, есть ли уже элемент с таким именем в этой папке у этого пользователя.
    exclude_id — исключить элемент (при переименовании).

    ВАЖНО: сравнение регистронезависимое делаем в Python,
    потому что SQLite lower() не работает с кириллицей.
    """
    target = name.strip().lower()

    # Забираем все элементы этой папки (их немного)
    query = CloudFile.query.filter_by(
        owner_id=owner_id,
        parent_id=parent_id,
        is_trashed=False,
    )

    if exclude_id is not None:
        query = query.filter(CloudFile.id != exclude_id)

    for item in query.all():
        if item.name.strip().lower() == target:
            return True

    return False


def create_folder(owner_id, name, parent_id=None):
    """
    Создаёт папку.
    Возвращает (ok: bool, result: CloudFile|str).
      ok=True  → result = объект CloudFile
      ok=False → result = текст ошибки
    """
    # 1. Валидация имени
    ok, error = validate_name(name)
    if not ok:
        return False, error

    name = name.strip()

    # 2. Проверка родителя
    if parent_id is not None:
        parent = get_folder(owner_id, parent_id)
        if not parent:
            return False, 'Родительская папка не найдена'
    else:
        parent = None

    # 3. Проверка дубликата
    if name_exists(owner_id, parent_id, name):
        return False, f'Элемент с именем «{name}» уже существует'

    # 4. Создаём
    folder = CloudFile(
        owner_id=owner_id,
        parent_id=parent_id,
        name=name,
        is_folder=True,
        size=0,
    )
    db.session.add(folder)
    db.session.commit()

    return True, folder

def rename_item(owner_id, item_id, new_name):
    """
    Переименовывает файл или папку.

    Возвращает (ok: bool, result: CloudFile|str).
      ok=True  → result = обновлённый объект CloudFile
      ok=False → result = текст ошибки
    """
    # 1. Валидация имени
    ok, error = validate_name(new_name)
    if not ok:
        return False, error

    new_name = new_name.strip()

    # 2. Находим элемент (файл или папка), проверяем владельца
    item = get_item(owner_id, item_id, allow_trashed=False)
    if not item:
        return False, 'Элемент не найден'

    # 3. Если имя то же самое — ничего не делаем (но возвращаем ok)
    if item.name == new_name:
        return True, item

    # 4. Проверка дубликата в той же папке
    if name_exists(owner_id, item.parent_id, new_name, exclude_id=item.id):
        return False, f'Элемент с именем «{new_name}» уже существует'

    # 5. Обновляем
    item.name = new_name
    item.updated_at = datetime.utcnow()
    db.session.commit()

    return True, item

def move_item(owner_id, item_id, new_parent_id):
    """
    Перемещает элемент (файл или папку) в новую родительскую папку.

    new_parent_id=None → переместить в корень пользователя.

    Возвращает (ok: bool, result: CloudFile|str).
    """
    # 1. Находим элемент
    item = get_item(owner_id, item_id, allow_trashed=False)
    if not item:
        return False, 'Элемент не найден'

    # 2. Проверяем нового родителя
    if new_parent_id is not None:
        new_parent = get_folder(owner_id, new_parent_id)
        if not new_parent:
            return False, 'Папка назначения не найдена'

        # Нельзя переместить в саму себя
        if new_parent.id == item.id:
            return False, 'Нельзя переместить в саму себя'

        # Если перемещаем папку — нельзя в её потомка
        if item.is_folder:
            if _is_descendant_of(new_parent, item):
                return False, 'Нельзя переместить папку в собственную подпапку'

    # 3. Проверка на то же место (ничего не делаем)
    if item.parent_id == new_parent_id:
        return True, item  # уже там

    # 4. Проверка дубликата имени в новой папке
    if name_exists(owner_id, new_parent_id, item.name, exclude_id=item.id):
        return False, f'В целевой папке уже есть элемент с именем «{item.name}»'

    # 5. Обновляем
    item.parent_id = new_parent_id
    item.updated_at = datetime.utcnow()
    db.session.commit()

    return True, item


def _is_descendant_of(item, ancestor):
    """
    Проверяет, что item — потомок ancestor (на любом уровне).
    Если item == ancestor → False (это не потомок, это тот же элемент).
    """
    if item.id == ancestor.id:
        return False

    current = item
    guard = 0
    while current.parent_id is not None and guard < 100:
        if current.parent_id == ancestor.id:
            return True
        current = CloudFile.query.get(current.parent_id)
        if current is None:
            break
        guard += 1

    return False

def _collect_descendants(item):
    """
    Рекурсивно собирает элемент и всех его потомков (включая сам item).
    Возвращает список CloudFile.
    """
    result = [item]

    if item.is_folder:
        children = CloudFile.query.filter_by(parent_id=item.id).all()
        for child in children:
            result.extend(_collect_descendants(child))

    return result


def trash_item(owner_id, item_id):
    """
    Мягкое удаление: помещает элемент и всех потомков в корзину.

    - is_trashed=True, trashed_at=now()
    - Связанные CloudShare удаляются (публичные ссылки перестают работать)

    Возвращает (ok: bool, result: dict|str).
      ok=True  → result = {'item': <CloudFile>, 'count': N}
                 где N — сколько всего элементов помечено
      ok=False → result = текст ошибки
    """
    # 1. Находим элемент
    item = get_item(owner_id, item_id, allow_trashed=False)
    if not item:
        return False, 'Элемент не найден'

    # 2. Собираем всё поддерево
    descendants = _collect_descendants(item)

    # 3. Помечаем
    now = datetime.utcnow()
    for node in descendants:
        node.is_trashed = True
        node.trashed_at = now

    # 4. Удаляем связанные CloudShare
    #    (запрос по file_id для всех descendants)
    descendant_ids = [d.id for d in descendants]
    if descendant_ids:
        CloudShare.query.filter(
            CloudShare.file_id.in_(descendant_ids)
        ).delete(synchronize_session=False)

    # 5. Сохраняем
    db.session.commit()

    return True, {
        'item': item,
        'count': len(descendants),
    }

def list_trash(owner_id):
    """
    Возвращает список «корневых» элементов корзины:
    - файлы, у которых parent НЕ в корзине (или отсутствует)
    - папки, у которых parent НЕ в корзине (или отсутствует)

    Так, если папка удалена — внутри неё элементы НЕ показываются отдельно,
    потому что они «скрыты» под папкой.

    Сортировка: сначала папки, потом файлы, внутри — по дате удаления (свежие вверху).
    """
    # Все удалённые элементы пользователя
    trashed = CloudFile.query.filter_by(
        owner_id=owner_id,
        is_trashed=True,
    ).all()

    if not trashed:
        return []

    # Собираем ID всех удалённых — чтобы понять, активен ли родитель
    trashed_ids = {item.id for item in trashed}

    # Оставляем только «корневые» элементы корзины
    roots = []
    for item in trashed:
        # Если parent_id = None — родитель корень, элемент виден
        if item.parent_id is None:
            roots.append(item)
        # Если parent_id НЕ в корзине — родитель активен, элемент виден
        elif item.parent_id not in trashed_ids:
            roots.append(item)
        # Иначе — родитель тоже в корзине, элемент скрыт под ним

    # Сортировка: папки вперёд, внутри — по trashed_at (свежие вверху)
    roots.sort(key=lambda x: (
        not x.is_folder,                          # папки (True→0) вперёд
        -(x.trashed_at.timestamp() if x.trashed_at else 0),   # свежие вверху
    ))

    return roots

def _restore_parents(owner_id, item):
    """
    Восстанавливает родителей элемента, если они в корзине.
    Возвращает количество восстановленных родителей.
    """
    count = 0
    parent_id = item.parent_id

    while parent_id is not None:
        parent = CloudFile.query.filter_by(
            id=parent_id,
            owner_id=owner_id,
        ).first()

        if not parent:
            # Родитель отсутствует — нечего восстанавливать
            break

        if not parent.is_trashed:
            # Родитель уже активен — всё ок, дальше не идём
            break

        # Родитель в корзине — восстанавливаем
        parent.is_trashed = False
        parent.trashed_at = None
        count += 1

        # Продолжаем вверх
        parent_id = parent.parent_id

    return count


def restore_item(owner_id, item_id):
    """
    Восстанавливает элемент из корзины.

    - Если родитель (или родители вверх) в корзине — восстанавливаем и их.
    - Если это папка — восстанавливаем всех её потомков.

    Возвращает (ok: bool, result: dict|str).
      ok=True  → {'item': <CloudFile>, 'count': N} — сколько всего восстановлено
      ok=False → текст ошибки
    """
    # 1. Находим элемент (в корзине)
    item = CloudFile.query.filter_by(
        id=item_id,
        owner_id=owner_id,
        is_trashed=True,
    ).first()

    if not item:
        return False, 'Элемент не найден в корзине'

    # 2. Восстанавливаем родителей (если они в корзине)
    parents_count = _restore_parents(owner_id, item)

    # 3. Собираем всех потомков (включая сам item)
    descendants = _collect_descendants(item)

    # 4. Помечаем всё восстановленным
    for node in descendants:
        node.is_trashed = False
        node.trashed_at = None

    # 5. Сохраняем
    db.session.commit()

    return True, {
        'item': item,
        'count': len(descendants) + parents_count,
        'restored_parents': parents_count,
    }


def delete_item_permanently(owner_id, item_id):
    """
    Полное удаление: убирает записи из БД и файлы с диска.
    Работает как с элементами в корзине, так и с активными.

    Возвращает (ok: bool, result: dict|str).
      ok=True  → {'item': <CloudFile>, 'count': N, 'freed_bytes': M}
      ok=False → текст ошибки
    """
    import os
    from flask import current_app

    # 1. Находим элемент (любой — активный или в корзине)
    item = get_item(owner_id, item_id, allow_trashed=True)
    if not item:
        return False, 'Элемент не найден'

    # 2. Собираем всё поддерево
    descendants = _collect_descendants(item)

    # 3. Считаем освобождённое место (только файлы)
    freed_bytes = sum(
        d.size or 0 for d in descendants if not d.is_folder
    )

    # 4. Удаляем связанные CloudShare
    descendant_ids = [d.id for d in descendants]
    if descendant_ids:
        CloudShare.query.filter(
            CloudShare.file_id.in_(descendant_ids)
        ).delete(synchronize_session=False)

    # 5. Собираем пути файлов для удаления с диска
    user_dir = os.path.join(
        current_app.config['CLOUD_DATA_DIR'],
        str(owner_id),
    )
    file_paths = []
    for d in descendants:
        if not d.is_folder and d.stored_name:
            path = os.path.join(user_dir, d.stored_name)
            # Защита от path traversal
            abs_path = os.path.abspath(path)
            abs_dir = os.path.abspath(user_dir)
            if abs_path.startswith(abs_dir + os.sep):
                file_paths.append(abs_path)

    # 6. Удаляем записи из БД
    #    Порядок важен: сначала потомки, потом корень (для FK на parent_id)
    #    Но SQLAlchemy сам разберётся через cascade, если мы удалим корень.
    #    Проще: удалить всё явно.
    for d in descendants:
        db.session.delete(d)

    db.session.commit()

    # 7. Удаляем файлы с диска (после commit — чтобы БД была консистентна)
    removed_files = 0
    for path in file_paths:
        try:
            os.remove(path)
            removed_files += 1
        except FileNotFoundError:
            # Файла уже нет — не страшно
            pass
        except OSError as e:
            # Другая ошибка (права, занят и т.д.) — логируем, продолжаем
            print(f'[delete] Не удалось удалить {path}: {e}')

    return True, {
        'item': item,
        'count': len(descendants),
        'freed_bytes': freed_bytes,
        'removed_files': removed_files,
    }


 # =============================================================
# ПУБЛИЧНЫЕ ССЫЛКИ (ШАРИНГ)
# =============================================================

def create_share(owner_id, item_id):
    """
    Создаёт публичную ссылку на файл или папку.

    Возвращает (ok: bool, result: CloudShare|str).
      ok=True  → result = объект CloudShare
      ok=False → result = текст ошибки
    """
    # 1. Находим элемент
    item = get_item(owner_id, item_id, allow_trashed=False)
    if not item:
        return False, 'Элемент не найден'

    # 2. Генерируем уникальный токен
    #    32 байта → ~43 символа base64url. Практически неугадываемо.
    for _ in range(10):   # попытки на случай коллизии (маловероятно)
        token = secrets.token_urlsafe(32)
        if not CloudShare.query.filter_by(token=token).first():
            break
    else:
        return False, 'Не удалось сгенерировать токен, попробуйте ещё раз'

    # 3. Создаём запись
    share = CloudShare(
        file_id=item.id,
        token=token,
        created_by_id=owner_id,
    )
    db.session.add(share)
    db.session.commit()

    return True, share


def get_share_by_token(token):
    """
    Находит CloudShare по токену.
    Возвращает CloudShare или None.
    Проверяет срок действия / лимит скачиваний.
    """
    if not token:
        return None

    share = CloudShare.query.filter_by(token=token).first()
    if not share:
        return None

    if share.is_expired():
        return None

    return share


def list_shares(owner_id):
    """
    Возвращает список всех публичных ссылок пользователя.
    Сортировка — свежие вверху.
    """
    return (
        CloudShare.query
        .filter_by(created_by_id=owner_id)
        .order_by(CloudShare.created_at.desc())
        .all()
    )


def revoke_share(owner_id, share_id):
    """
    Удаляет публичную ссылку.
    Возвращает (ok: bool, result: CloudShare|str).
    """
    share = CloudShare.query.filter_by(
        id=share_id,
        created_by_id=owner_id,
    ).first()

    if not share:
        return False, 'Ссылка не найдена'

    db.session.delete(share)
    db.session.commit()

    return True, share


def increment_share_download(share):
    """Увеличивает счётчик скачиваний и сохраняет."""
    share.download_count = (share.download_count or 0) + 1
    db.session.commit()   

def count_trash(owner_id):
    """Возвращает количество элементов в корзине (всех, не только корневых)."""
    return CloudFile.query.filter_by(
        owner_id=owner_id,
        is_trashed=True,
    ).count()

# =============================================================
# ЗАГРУЗКА ФАЙЛОВ
# =============================================================

def _user_dir(owner_id):
    """Возвращает путь к папке пользователя, создаёт если нет."""
    base = current_app.config['CLOUD_DATA_DIR']
    path = os.path.join(base, str(owner_id))
    os.makedirs(path, exist_ok=True)
    return path


def _unique_display_name(owner_id, parent_id, name):
    """
    Если файл с таким именем уже есть — добавляет ' (1)', ' (2)' и т.д.
    Работает с сохранением расширения: 'file.txt' → 'file (1).txt'
    """
    if not name_exists(owner_id, parent_id, name):
        return name

    # Отделяем расширение
    stem, ext = os.path.splitext(name)
    # ext уже с точкой: '.txt'
    for i in range(1, 1000):
        candidate = f'{stem} ({i}){ext}'
        if not name_exists(owner_id, parent_id, candidate):
            return candidate

    # На всякий случай — если 999 попыток не хватило
    return f'{stem} ({uuid.uuid4().hex[:6]}){ext}'


def save_uploaded_file(owner_id, file_storage, parent_id=None):
    """
    Сохраняет загруженный файл.

    Возвращает (ok: bool, result: CloudFile|str).
      ok=True  → result = объект CloudFile
      ok=False → result = текст ошибки
    """
    # 1. Имя
    original_name = (file_storage.filename or '').strip()
    ok, error = validate_name(original_name)
    if not ok:
        return False, error

    # 2. Родитель
    if parent_id is not None:
        parent = get_folder(owner_id, parent_id)
        if not parent:
            return False, 'Родительская папка не найдена'

    # 3. Размер (узнаём через seek)
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    if size == 0:
        return False, 'Файл пустой'

    # 4. Квота
    ok, quota = has_enough_space_by_id(owner_id, size)
    if not ok:
        return False, (
            f'Недостаточно места. Занято {format_bytes(quota["used"])} '
            f'из {format_bytes(quota["total"])}, '
            f'нужно ещё {format_bytes(size)}'
        )

    # 5. Уникальное имя на диске
    ext = os.path.splitext(original_name)[1].lower().lstrip('.')
    stored_name = uuid.uuid4().hex
    if ext:
        stored_name += '.' + ext

    # 6. Физический путь
    user_dir = _user_dir(owner_id)
    save_path = os.path.join(user_dir, stored_name)

    # 7. Сохранение
    try:
        file_storage.save(save_path)
    except Exception as e:
        return False, f'Ошибка сохранения файла: {e}'

    # 8. Уникальное отображаемое имя
    display_name = _unique_display_name(owner_id, parent_id, original_name)

    # 9. MIME-тип
    mime_type, _ = mimetypes.guess_type(original_name)
    if not mime_type:
        mime_type = 'application/octet-stream'

    # 10. Запись в БД
    try:
        record = CloudFile(
            owner_id=owner_id,
            parent_id=parent_id,
            name=display_name,
            is_folder=False,
            stored_name=stored_name,
            size=size,
            mime_type=mime_type,
        )
        db.session.add(record)
        db.session.commit()
    except Exception as e:
        # Если БД упала — удаляем файл с диска, чтобы не было мусора
        try:
            os.remove(save_path)
        except OSError:
            pass
        return False, f'Ошибка записи в БД: {e}'

    return True, record


def has_enough_space_by_id(owner_id, size_bytes):
    """
    Проверка квоты по owner_id (не требует объекта User).
    Возвращает (ok: bool, info: dict).
    """
    used = get_used_bytes(owner_id, include_trashed=True)

    # Получаем квоту из User
    user = User.query.get(owner_id)
    total = (user.quota_bytes if user else 0) or 0

    ok = (used + size_bytes) <= total

    return ok, {
        'used': used,
        'total': total,
        'free': max(0, total - used),
        'percent': round(used / total * 100, 1) if total > 0 else 0,
    }

def build_breadcrumbs(owner_id, folder_id):
    """
    Строит «хлебные крошки» от корня до folder_id.

    Возвращает список dict-ов:
        [{'id': None, 'name': 'Мой диск'},
         {'id': 5, 'name': 'Документы'},
         {'id': 12, 'name': 'Отчёты'}]

    Безопасность: каждая папка проверяется на owner_id.
    """
    crumbs = [{'id': None, 'name': 'Мой диск'}]

    if folder_id is None:
        return crumbs

    # Собираем цепочку от текущей папки вверх
    chain = []
    current_id = folder_id
    guard = 0   # защита от бесконечного цикла (если что-то сломается)

    while current_id and guard < 100:
        folder = get_folder(owner_id, current_id)
        if not folder:
            break
        chain.append({'id': folder.id, 'name': folder.name})
        current_id = folder.parent_id
        guard += 1

    # Разворачиваем (от корня вниз)
    chain.reverse()
    crumbs.extend(chain)
    return crumbs


# =============================================================
# КВОТЫ
# =============================================================

def get_used_bytes(owner_id, include_trashed=True):
    """
    Занятое место пользователя в байтах.
    По умолчанию включает файлы в корзине (они реально лежат на диске).
    """
    query = db.session.query(func.coalesce(func.sum(CloudFile.size), 0))\
        .filter(
            CloudFile.owner_id == owner_id,
            CloudFile.is_folder == False,   # noqa: E712
        )

    if not include_trashed:
        query = query.filter(CloudFile.is_trashed == False)   # noqa: E712

    return int(query.scalar() or 0)


def get_trashed_bytes(owner_id):
    """Занятое место только файлами в корзине."""
    result = db.session.query(func.coalesce(func.sum(CloudFile.size), 0))\
        .filter(
            CloudFile.owner_id == owner_id,
            CloudFile.is_folder == False,   # noqa: E712
            CloudFile.is_trashed == True,   # noqa: E712
        ).scalar()
    return int(result or 0)


def get_quota_info(user):
    """
    Возвращает dict с информацией о квоте:
        {
            'used': int,           # байт (с корзиной)
            'used_active': int,    # байт (без корзины)
            'trashed': int,        # байт (только корзина)
            'total': int,          # байт (квота)
            'free': int,           # байт (свободно)
            'percent': float,      # 0..100 (использовано от квоты)
        }
    """
    used = get_used_bytes(user.id, include_trashed=True)
    trashed = get_trashed_bytes(user.id)
    used_active = used - trashed
    total = user.quota_bytes or 0
    free = max(0, total - used)
    percent = (used / total * 100) if total > 0 else 0

    return {
        'used': used,
        'used_active': used_active,
        'trashed': trashed,
        'total': total,
        'free': free,
        'percent': round(percent, 1),
    }


def has_enough_space(user, size_bytes):
    """
    Проверяет, хватит ли места для загрузки файла размером size_bytes.
    Возвращает (ok: bool, info: dict).
    """
    info = get_quota_info(user)
    ok = (info['used'] + size_bytes) <= info['total']
    return ok, info


# =============================================================
# УТИЛИТЫ
# =============================================================

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

# =============================================================
# ИКОНКИ ПО ТИПУ ФАЙЛА
# =============================================================

# Точные расширения → (иконка, цвет)
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
    Если тип не определён — общая иконка файла.

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