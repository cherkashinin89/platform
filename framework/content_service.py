# content_service.py - управление реестром использования облачных файлов
#
# Регистрирует связи между облачными файлами (cloud_file) и контентом
# (статьи, страницы, альбомы). Нужно для:
#   - блокировки удаления используемых файлов;
#   - поиска «где используется файл»;
#   - автоочистки файлов, оставшихся без использования.
#
# Соглашение: облачные файлы в HTML-контенте ссылаются как /media/<file_id>.
import re
from models import db, FileUsage, CloudFile


# Регулярка для поиска ссылок на /media/<id>
# Покрывает случаи: <img src="/media/42">, <a href="/media/42">,
# а также «голые» упоминания в тексте.
_MEDIA_RE = re.compile(r'/media/(\d+)')


def extract_file_ids(html):
    """
    Извлекает уникальные file_id из HTML-контента.
    Возвращает set[int].
    """
    if not html:
        return set()
    return {int(m) for m in _MEDIA_RE.findall(html)}


def register_file_usages(content_html, entity_type, entity_id, user_id):
    """
    Перестраивает FileUsage для сущности (article/page).

    Удаляет старые записи этой сущности, создаёт новые на основе
    всех /media/<id>, найденных в HTML. Файлы, которых нет в БД
    (или которые не CloudFile), игнорируются.

    :param content_html: HTML-контент
    :param entity_type: 'article' | 'page' (для альбомов — отдельно)
    :param entity_id: id сущности
    :param user_id: id того, кто сохраняет (для аудита)
    :return: количество зарегистрированных связей (int)
    """
    # 1. Удаляем старые связи этой сущности
    FileUsage.query.filter_by(
        entity_type=entity_type,
        entity_id=entity_id,
    ).delete(synchronize_session=False)

    # 2. Собираем новые file_id
    file_ids = extract_file_ids(content_html)
    if not file_ids:
        return 0

    # 3. Проверяем существование файлов (только облачные, не корзина)
    existing_ids = {
        row[0] for row in
        db.session.query(CloudFile.id)
        .filter(CloudFile.id.in_(file_ids))
        .filter(CloudFile.is_folder.is_(False))
        .all()
    }

    # 4. Создаём записи
    created = 0
    for fid in existing_ids:
        db.session.add(FileUsage(
            file_id=fid,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
        ))
        created += 1
    return created


def unregister_file_usages(entity_type, entity_id):
    """
    Удаляет все FileUsage для сущности (при удалении статьи/страницы/альбома).
    Возвращает количество удалённых записей.
    """
    deleted = FileUsage.query.filter_by(
        entity_type=entity_type,
        entity_id=entity_id,
    ).delete(synchronize_session=False)
    return int(deleted or 0)


def register_album_photos(album_id, file_ids, user_id):
    """
    Регистрирует FileUsage для фото альбома.
    Вызывается при добавлении фото в альбом.

    :param album_id: id альбома
    :param file_ids: список cloud_file.id
    :param user_id: кто добавляет
    :return: количество новых записей
    """
    created = 0
    for fid in file_ids:
        existing = FileUsage.query.filter_by(
            file_id=fid,
            entity_type='album',
            entity_id=album_id,
        ).first()
        if existing:
            continue
        db.session.add(FileUsage(
            file_id=fid,
            entity_type='album',
            entity_id=album_id,
            user_id=user_id,
        ))
        created += 1
    return created


def check_file_usage(file_id):
    """
    Возвращает список мест, где используется файл.
    Формат: [{'type': 'article', 'id': 5, 'title': '...'}, ...]
    """
    from models import Article, Page, Album
    usages = FileUsage.query.filter_by(file_id=file_id).all()
    result = []
    for u in usages:
        item = {'type': u.entity_type, 'id': u.entity_id, 'title': '—'}
        if u.entity_type == 'article':
            a = Article.query.get(u.entity_id)
            if a:
                item['title'] = a.title
            else:
                continue
        elif u.entity_type == 'page':
            p = Page.query.get(u.entity_id)
            if p:
                item['title'] = p.title
            else:
                continue
        elif u.entity_type == 'album':
            al = Album.query.get(u.entity_id)
            if al:
                item['title'] = al.title
            else:
                continue
        result.append(item)
    return result


def find_unused_files(owner_id=None, folder_file_ids=None):
    """
    Находит облачные файлы, которые НЕ используются ни в одном контенте.

    :param owner_id: ограничить владельцем (None = все)
    :param folder_file_ids: ограничить списком id (для чистки конкретной папки)
    :return: список CloudFile
    """
    q = (
        CloudFile.query
        .filter(CloudFile.is_folder.is_(False))
        .filter(CloudFile.is_trashed.is_(False))
    )
    if owner_id is not None:
        q = q.filter(CloudFile.owner_id == owner_id)
    if folder_file_ids:
        q = q.filter(CloudFile.id.in_(folder_file_ids))

    # Список id, которые где-то используются
    used_subq = db.session.query(FileUsage.file_id).distinct()
    used_ids = {row[0] for row in used_subq.all()}

    return [f for f in q.all() if f.id not in used_ids]