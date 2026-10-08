# search_service.py - Поиск по сайту (статьи, страницы, файлы)
"""
Абстракция над поиском.

ВАЖНО: фильтрация идёт на стороне Python, а не SQL.
Причина — SQLite не умеет регистронезависимый LIKE для кириллицы
(lower()/upper() в SQLite работают только с ASCII).

Для текущих объёмов (десятки-сотни записей) это оптимально.
При переезде на PostgreSQL внутренности можно заменить на tsvector
или pg_trgm — интерфейс функций останется прежним.
"""
import re
from html import unescape
from markupsafe import Markup, escape
from models import Article, Page, UploadedFile, Photo, Album


# =============================================================
# УТИЛИТЫ ДЛЯ ТЕКСТА
# =============================================================

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def strip_html(html):
    """Убирает HTML-теги и лишние пробелы, декодирует сущности."""
    if not html:
        return ''
    text = _TAG_RE.sub(' ', html)
    text = unescape(text)
    text = _WS_RE.sub(' ', text)
    return text.strip()


def make_snippet(text, query, context=80):
    """
    Возвращает фрагмент текста вокруг первого совпадения с query.
    Многоточие по краям, если фрагмент вырезан.
    Поиск регистронезависимый (Python lower).
    """
    if not text:
        return ''
    if not query:
        return text[:context * 2] + ('…' if len(text) > context * 2 else '')

    low_text = text.lower()
    low_q = query.lower()
    pos = low_text.find(low_q)

    if pos == -1:
        return text[:context * 2] + ('…' if len(text) > context * 2 else '')

    start = max(0, pos - context)
    end = min(len(text), pos + len(query) + context)

    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(text) else ''
    return prefix + text[start:end] + suffix


def highlight(text, query):
    """
    Оборачивает совпадения с query в <mark>.
    Регистронезависимо, экранирует HTML.
    """
    if not text or not query:
        return text

    safe = str(escape(text))
    # re.escape защищает от спецсимволов; re.IGNORECASE корректно работает с кириллицей в Python
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    result = pattern.sub(lambda m: f'<mark>{m.group(0)}</mark>', safe)
    return Markup(result)


def _contains(text, query):
    """Регистронезависимая проверка вхождения (для кириллицы)."""
    if not text or not query:
        return False
    return query.lower() in text.lower()


def _count_occurrences(text, query):
    """Количество вхождений (регистронезависимо)."""
    if not text or not query:
        return 0
    return text.lower().count(query.lower())


def score_text(text, query):
    """
    Простейшая оценка релевантности:
    - есть совпадение: +10
    - количество вхождений: +1 каждое
    - короткий текст: бонус за плотность
    """
    count = _count_occurrences(text, query)
    if count == 0:
        return 0
    score = 10 + count
    density_bonus = min(10, max(0, 500 // max(1, len(text))))
    return score + density_bonus


# =============================================================
# СБОР ПУБЛИЧНЫХ ФАЙЛОВ (Вариант B)
# =============================================================

_UPLOADS_RE = re.compile(r'/uploads/([A-Za-z0-9_\-\.]+)')


def get_public_file_names():
    """
    Возвращает set имён stored_name файлов, которые реально опубликованы:
    - упомянуты в content опубликованных статей
    - упомянуты в content страниц
    - входят в опубликованные альбомы (Photo.file)
    """
    public = set()

    # 1. Статьи (только опубликованные)
    articles = Article.query.filter_by(is_published=True).all()
    for a in articles:
        public.update(_UPLOADS_RE.findall(a.content or ''))

    # 2. Страницы (все публичны)
    pages = Page.query.all()
    for p in pages:
        public.update(_UPLOADS_RE.findall(p.content or ''))

    # 3. Фото из опубликованных альбомов
    photos = (
        Photo.query
        .join(Album, Photo.album_id == Album.id)
        .filter(Album.is_published == True)
        .all()
    )
    for ph in photos:
        if ph.file and ph.file.stored_name:
            public.add(ph.file.stored_name)

    return public


# =============================================================
# ПУБЛИЧНЫЙ ПОИСК
# =============================================================

def search_articles(query, limit=20):
    """Поиск по опубликованным статьям: title, summary, content."""
    if not query:
        return []

    articles = Article.query.filter_by(is_published=True).all()

    results = []
    for a in articles:
        plain = strip_html(a.content or '')

        title_match = _contains(a.title, query)
        summary_match = _contains(a.summary, query)
        content_match = _contains(plain, query)

        if not (title_match or summary_match or content_match):
            continue

        # Сниппет — из того места, где нашли
        if content_match:
            snippet_src = plain
        elif summary_match:
            snippet_src = a.summary or ''
        else:
            snippet_src = a.title or ''

        score = (
            score_text(a.title or '', query) * 3
            + score_text(a.summary or '', query) * 2
            + score_text(plain, query)
        )

        # Авторы
        try:
            authors_list = list(a.authors)
        except Exception:
            authors_list = []

        results.append({
            'type': 'article',
            'obj': a,
            'title': a.title,
            'snippet': make_snippet(snippet_src, query),
            'score': score,
            'url': f'/article/{a.id}',
            'meta': {
                'date': a.created_at.strftime('%d.%m.%Y') if a.created_at else '',
                'author': ', '.join(u.username for u in authors_list),
            },
        })

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def search_pages(query, limit=20):
    """Поиск по страницам: title, content."""
    if not query:
        return []

    pages = Page.query.all()

    results = []
    for p in pages:
        plain = strip_html(p.content or '')

        title_match = _contains(p.title, query)
        content_match = _contains(plain, query)

        if not (title_match or content_match):
            continue

        snippet_src = plain if content_match else (p.title or '')

        score = score_text(p.title or '', query) * 3 + score_text(plain, query)

        results.append({
            'type': 'page',
            'obj': p,
            'title': p.title,
            'snippet': make_snippet(snippet_src, query),
            'score': score,
            'url': f'/page/{p.slug}',
            'meta': {},
        })

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def search_files(query, limit=20, public_only=True):
    """
    Поиск по файлам. public_only=True — только реально опубликованные (Вариант B).
    public_only=False — все (для админки).
    """
    if not query:
        return []

    files = UploadedFile.query.all()

    public_names = get_public_file_names() if public_only else None

    results = []
    for f in files:
        if public_only and f.stored_name not in public_names:
            continue

        name_match = _contains(f.original_name, query)
        desc_match = _contains(f.description, query)

        if not (name_match or desc_match):
            continue

        score = score_text(f.original_name or '', query) * 2
        if f.description:
            score += score_text(f.description, query)

        results.append({
            'type': 'file',
            'obj': f,
            'title': f.original_name,
            'snippet': f.description or f'{f.file_type} • {f.size_human()}',
            'score': score,
            'url': f'/uploads/{f.stored_name}',
            'meta': {
                'size': f.size_human(),
                'date': f.uploaded_at.strftime('%d.%m.%Y') if f.uploaded_at else '',
            },
        })

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def search_all(query, limit_each=10):
    """Полный публичный поиск: статьи + страницы + файлы."""
    return {
        'articles': search_articles(query, limit=limit_each),
        'pages': search_pages(query, limit=limit_each),
        'files': search_files(query, limit=limit_each, public_only=True),
    }