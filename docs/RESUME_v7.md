# Резюме проекта platform — v7
**Дата:** 2026-10-11
**Статус:** W3 полностью завершён. Готовы к W34 или W40.

---

## 0. КРАТКОЕ СОСТОЯНИЕ

- Монорепо `platform` работает на проде (`192.168.2.19`).
- W3 (прикрепление файлов облака к статьям/страницам) — полностью завершён.
- W31, W32, W36, W37, W38+W39 — завершены.
- Осталось:
  - W34 — делегирование облака (при удалении пользователя).
  - W33 — утилита сканирования ShareAttach (отложена).
  - W35 — закрытая шара (отложена).
  - W40 — подготовка к боевому (HTTPS, сессии, поддомены).

---

## 1. СТЕК И ИНФРАСТРУКТУРА

### Backend
- Python 3.13.5
- Flask 3.0.0, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.2.1, Flask-Migrate 4.0.7
- PostgreSQL 17.11 + psycopg[binary]==3.3.6
- Pillow 11.3.0 / 12.3.0, psutil 5.9.8, python-dotenv 1.0.1, email_validator 2.1.1
- requests 2.x (добавлен для внутренних запросов framework→cloud)
- gunicorn 21.2.0

### Frontend
- Bootstrap 5.3.0, Bootstrap Icons 1.11.0, TinyMCE 7, Sortable.js 1.15.2 — все локально.
- Vanilla JS.

### Инфраструктура
- Сервер: RV511 (i3 M380, 6 ГБ RAM, HDD 1 ТБ), Debian 13 Trixie x86_64, хостнейм testprod2.
- IP: 192.168.2.19, юзер deploy.
- Директория монорепо: /home/deploy/apps/platform/
- Nginx 1.26.3 (reverse proxy):
  - :80 → 127.0.0.1:5000 (framework).
  - :5001 → 127.0.0.1:5002 (cloud).
- Gunicorn: 2 воркера на каждом сервисе.
- systemd: framework.service, cloud.service (в /etc/systemd/system/).
- WireGuard на роутере TP-Link Archer AX55.
- Внешняя флешка BACKUP (exfat, UUID FFBB-A34E, 3.8 ГБ) — /mnt/backup.

### Реквизиты (тестовые, сменить при боевом)
- Админка: admin / admin123.
- Пароль deploy (SSH/sudo): Zxfg5h!!.
- Пароль PostgreSQL: myframework_dev_password.
- БД: myframework, юзер: myframework.
- SECRET_KEY=358b1c3dc829c638f2111058148bfd70760650e783d9c136580e2c45cf5691f1.
- INTERNAL_API_KEY=a510093a20099456fdfcc1effb6ff15285fb4b49bfcb517fab4580de1405c003.

---

## 2. СТРУКТУРА МОНОРЕПО
/home/deploy/apps/platform/ ← git: github.com/cherkashinin89/platform
├── README.md
├── .gitignore
├── .env ← ОДИН общий
│
├── core/ ← общий пакет (pip install -e ../core)
│ ├── init.py
│ ├── pyproject.toml
│ ├── models.py
│ ├── extensions.py
│ ├── auth.py
│ ├── config.py
│ ├── cloud_utils.py
│ ├── content_service.py
│ ├── file_utils.py
│ ├── image_utils.py
│ ├── slug_utils.py
│ ├── system_stats.py
│ ├── backup_utils.py
│ ├── files_icons.py
│ ├── templates/
│ │ ├── core_base.html
│ │ └── partials/
│ │ ├── header.html
│ │ ├── file_manager_modal.html ← W3
│ │ ├── attached_file.html
│ │ ├── folder_view.html ← W3
│ │ └── ...
│ └── static/
│ ├── css/style.css
│ ├── themes/{default,dark}/style.css
│ ├── js/
│ │ ├── attached-files.js ← W3
│ │ └── toast.js ← W31
│ └── vendor/{bootstrap,bootstrap-icons}/
│
├── framework/ ← сайт + админка
│ ├── app.py
│ ├── config.py
│ ├── forms.py
│ ├── search_service.py
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── migrations/versions/
│ │ ├── def34305bcda_initial_schema_postgresql_baseline.py
│ │ ├── bec349bf7b84_w3_file_usage_audit_log_archive_.py
│ │ ├── b3fce6fbe4b6_w3_photo_file_id_cloud_file_id.py
│ │ └── 9f246cb32d6e_w3_share_attach.py
│ ├── venv/
│ ├── uploads/
│ ├── archives/
│ ├── templates/
│ │ ├── base.html
│ │ ├── article.html, page.html, index.html, articles_list.html, search.html, login.html
│ │ ├── public_share.html ← W3
│ │ ├── public_share_invalid.html
│ │ ├── _pagination.html
│ │ ├── partials/
│ │ │ ├── folder_view.html ← W3
│ │ │ ├── attached_file.html
│ │ │ ├── articles_grid.html
│ │ │ ├── _menu_macros.html
│ │ │ └── recent_articles.html
│ │ ├── gallery/{index,album}.html
│ │ └── admin/
│ │ ├── base_admin.html
│ │ ├── article_form.html, page_form.html
│ │ ├── users.html, settings.html, files.html, albums.html
│ │ └── ...
│ └── static/
│ ├── tinymce/
│ └── vendor/sortable.min.js
│
├── cloud/ ← облако
│ ├── app.py
│ ├── cloud_service.py
│ ├── config.py
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── venv/
│ ├── cloud_data/
│ ├── templates/
│ │ ├── base_cloud.html
│ │ ├── index.html ← W37
│ │ ├── shares.html
│ │ ├── attached.html ← W36
│ │ ├── trash.html
│ │ └── public_share.html, public_share_invalid.html
│ └── static/css/cloud.css
│
├── mail/ ← заготовка
│
├── docs/
│ ├── W3.md
│ └── RESUME_v7.md ← этот файл
│
└── deploy/
├── README.md
├── setup.sh
├── env.example
├── nginx/{framework,cloud}.conf
├── systemd/{framework,cloud}.service
└── sudoers/{framework-restart,framework-mount,cloud-restart}

text

---

## 3. МОДЕЛИ (core/models.py)

### Существующие
- User, Article, Page, MenuItem
- UploadedFile, Album, Photo, SiteSettings
- CloudFile (owner_id, parent_id, is_folder, stored_name, mime_type, size, is_trashed, trashed_at)
- CloudShare (token, file_id, created_by_id, expires_at, password_hash, download_count, max_downloads)
- FileUsage, AuditLog

### W3: ShareAttach (создана миграцией 9f246cb32d6e)

```python
class ShareAttach(db.Model):
    __tablename__ = 'share_attach'
    __table_args__ = (
        db.CheckConstraint("target_type IN ('article', 'page')",
                           name='ck_share_attach_target_type'),
        db.Index('idx_share_attach_target', 'target_type', 'target_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(
        db.Integer,
        db.ForeignKey('cloud_share.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    share = db.relationship(
        'CloudShare',
        backref=db.backref('attachments', passive_deletes=True),
        passive_deletes=True,
    )
Принципы:

Одна строка = одна связь (шара ↔ статья ИЛИ страница).

При удалении CloudShare — ShareAttach удаляются каскадно (FK + passive_deletes=True).

При удалении статьи/страницы — ShareAttach удаляются в коде.

4. W3 — ПРИКРЕПЛЕНИЕ ФАЙЛОВ К СТАТЬЯМ/СТРАНИЦАМ
4.1. API
Cloud:

Метод	Путь	Описание
POST	/api/internal-share/<file_id>	Создать/переиспользовать шару от имени пользователя. Заголовки X-Internal-Key, X-User-Id. @csrf.exempt.
Framework:

Метод	Путь	Описание
GET	/admin/api/cloud-tree	Дерево папок пользователя
GET	/admin/api/cloud-folder/<id>	Содержимое папки
GET	/admin/api/cloud-files	Список файлов и папок (is_folder, parent_id)
POST	/admin/api/attach-to-article	Создать шары + ShareAttach ({article_id?, page_id?, file_ids: []})
GET	/admin/api/check-attachments/<file_id>	Проверка привязок
GET	/article/<id>/folder/<folder_id>	AJAX-фрагмент папки
GET	/s/<token>	Публичная страница шары в framework
GET	/s/<token>/download	Скачать файл шары
GET	/s/<token>/download/<file_id>	Скачать файл из папки-шары
4.2. UI модалки
Файлы: core/templates/partials/file_manager_modal.html, core/static/js/attached-files.js

Двухпанельный лэйаут: слева дерево папок, справа плитки.

Адаптивный (min 800px, max 95%).

Дерево: корень «Мои файлы», sessionStorage для expandedIds.

Плитки: миниатюра для картинок, цветные иконки по типу (Word синий #0d6efd, Excel зелёный #198754, PowerPoint оранжевый #fd7e14, Архив фиолетовый #6f42c1, video красный #dc3545).

Чекбокс: серый → яркий при наведении → цветной при отметке.

Клик по файлу — выбрать; по папке — войти; по чекбоксу — выбрать.

Счётчик «Выбрано: N из M» + кнопки «Выбрать все» / «Снять все».

Кнопка «Прикрепить (N)».

Источник — только облако. Только свои файлы. Предупреждение при > 20.

4.3. UI статьи
До сохранения (в редакторе):

Плитка с классом is-temp (пунктир + бейдж «временно»).

data-file-id="42".

После сохранения:

Без is-temp, с data-share-token="<token>", href="/s/<token>".

Клик в статье:

Картинка → лайтбокс.

Документ → скачивание.

Папка → AJAX-навигация (фрагмент в main, кнопки «Назад»/«Крестик»).

Мёртвая шара → серая плитка (недоступно).

4.4. Логика сохранения
_процесс_attached_files_in_html:

Парсим HTML.

data-file-id → POST /api/internal-share/<file_id> → token.

Заменяем data-file-id → data-share-token, убираем is-temp, добавляем href="/s/<token>".

Создаём ShareAttach.

Удаляем ShareAttach, чьи токены пропали из HTML.

Удаляем CloudShare, если нет других ShareAttach.

При удалении статьи/страницы — удаляем ShareAttach + шары-сироты.
При копировании — та же шара, новая ShareAttach.

4.5. TinyMCE
javascript
tinymce.init({
    relative_urls: false,
    convert_urls: false,
    remove_script_host: false,
    toolbar: '... attachfile | code fullscreen | removeformat help',
    setup: function (editor) {
        editor.ui.registry.addButton('attachfile', {
            icon: 'upload',
            tooltip: 'Прикрепить из облака',
            onAction: function () {
                window.__activeEditor = editor;
                if (window.fmOpen) window.fmOpen();
            }
        });
    },
});
5. W31 — TOAST-УВЕДОМЛЕНИЯ
CSS: .app-toast-* в core/static/css/style.css (НЕ .toast — конфликт с Bootstrap).

JS: core/static/js/toast.js — window.showToast(message, type, duration).

Типы: success / danger / warning / info.

Позиция: правый-верхний угол, стек.

Стиль: тёмная карточка, цветная левая полоса, иконка, крестик.

Автозакрытие: 4 сек (danger — 6 сек).

Подключено в core_base.html.

Flash в base_admin.html, base.html, base_cloud.html заменены на showToast через {{ message|tojson }}.

В attached-files.js все alert() заменены на showToast(..., 'danger').

6. W32 — УБРАНЫ DEBUG-ЛОГИ
В framework/app.py удалены print('[DEBUG] ...') из context_processor.

7. W36 — ВКЛАДКА «ПРИКРЕПЛЕНО К СТАТЬЯМ» В ОБЛАКЕ
Новая функция list_attached_shares(owner_id) в cloud/cloud_service.py.

Новый маршрут /attached в cloud/app.py.

Новый шаблон cloud/templates/attached.html (стили items-table).

Навигация в base_cloud.html: Мои файлы | Ссылки | Прикреплено | Корзина.

Столбцы: Файл / папка, Прикреплено к, Дата, Действия.

8. W37 — ПЛИТКИ В ОБЛАКЕ + ПРОГРЕСС-БАР
cloud/templates/index.html: таблица → сетка .cloud-tiles с .fm-tile.

Размер папок: {{ item.size_human() if not item.is_folder else '—' }}.

Клик — выделение (задержка 250 мс, чтобы не конфликтовать с двойным).

Двойной клик — открыть (папка / скачать).

Чекбокс — toggle.

Drag&drop — на плитки-папки и на узлы дерева.

Кнопки действий (Поделиться, Переименовать, Удалить) — при наведении.

Прогресс-бар загрузки:

Каждый файл — отдельная строка.

Полоска + процент + статус (⏳ / 📤 / ✅ / ❌).

XMLHttpRequest (не fetch) — для upload.onprogress.

Отправка по одному файлу.

CSS в cloud/static/css/cloud.css: .upload-files-list, .file-item-bar.

9. W38+W39 — TRASH + ПРЕДУПРЕЖДЕНИЕ
W38:

trash_item в cloud_service.py — НЕ удаляет CloudShare.

get_share_by_token в core/cloud_utils.py — проверка is_trashed.

delete_item_permanently — удаляет CloudShare (как раньше).

Bug passive_deletes=True — устранён.

W39:

Cloud: новый маршрут /api/check-attachments/<file_id>.

Cloud: trashSelected в index.html проверяет привязки, показывает confirm.

ВНИМАНИЕ: удаление по иконке в строке не проверяет привязки. Учесть при рефакторинге UI.

Фикс двойных имён в shares.html — удалена дублирующая строка.

10. W34 — ДЕЛЕГИРОВАНИЕ ОБЛАКА (НЕ СДЕЛАНО)
Сценарий
Админ в «Пользователи» удаляет ivan ИЛИ меняет роль editor → user.

Что должно происходить
Проверить активы: файлы, шары, ShareAttach, статьи, страницы.

Модалка «Кому передать файлы?» — dropdown (по умолчанию — админ).

Создать у получателя папку «Унаследовано от <username> <дата>».

Перенести физические файлы.

Обновить owner_id, parent_id, CloudShare.created_by_id.

Обновить Article.authors.

Записать в AuditLog.

Удалить пользователя.

UI
В framework/templates/admin/users.html — кнопка «Удалить» → POST /admin/users/<id>/delete.

Если активы есть — модалка user_delete_modal.html.

Endpoint POST /admin/users/<id>/reassign.

Тест
Создать редактора ivan, залить файлы, прикрепить к статье.

Создать petr.

Удалить ivan → передать petr.

Проверить.

Оценка: 1–2 часа.

11. W40 — ПОДГОТОВКА К БОЕВОМУ (HTTPS / СЕССИИ / ПОДДОМЕНЫ)
Правки в core/config.py (закомментированы, активировать)
Строки 30–31:

python
# SESSION_COOKIE_SECURE = True
# SESSION_COOKIE_DOMAIN = '.site.ru'
Добавить:

python
from datetime import timedelta
...
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
Правки в framework/app.py и cloud/app.py
python
from flask import session

@app.before_request
def make_session_permanent():
    session.permanent = True
python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
SSL-план
Certbot + Let's Encrypt:

text
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d mysite.ru -d www.mysite.ru -d cloud.mysite.ru
Nginx: listen 443 ssl http2 + ssl_certificate + редирект с 80.

HSTS: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload.

Cookies: SESSION_COOKIE_SECURE=True, SESSION_COOKIE_DOMAIN='.mysite.ru'.

Уведомление в админке о сроке SSL.

Тест через SSL Labs (цель A).

Известные проблемы (починить при боевом)
Логаут + CSRF missing: браузерная сессия + токен. Решение — PERMANENT_SESSION_LIFETIME + session.permanent.

12. W33 — УТИЛИТА СКАНИРОВАНИЯ ShareAttach (ОТЛОЖЕНО)
Раздел в админке: /admin/attachments.

Список файлов с привязками.

Действия: отвязать, перейти, скачать.

Обратный отчёт: файлы-сироты.

Поиск.

Оценка: 1–2 часа.

13. W35 — ЗАКРЫТАЯ ШАРА (ОТЛОЖЕНО)
В CloudShare уже есть: password_hash, expires_at, max_downloads, download_count.

Добавить:

UI при создании шары (пароль, срок, лимит).

/s/<token> — форма ввода пароля при password_hash.

Проверка пароля + сессия доступа.

Сообщения «Ссылка истекла» / «Лимит скачиваний».

Оценка: 1–2 часа.

14. ИСТОРИЯ КОММИТОВ ЭТОЙ СЕССИИ
#	Задача	Коммит
W3	Этап 1: модель ShareAttach + миграция	db7da8d
W3	Этап 2: cloud internal-share	47dad68
W3	Этап 2: framework API (cloud-tree, cloud-folder, check-attachments)	713ff89
W3	Этап 2: framework attach-to-article	c4844eb
W3	Этап 2: cloud-files с папками + requests	c0da1d9
W3	Этап 3: новая модалка + /s/<token> в framework	c96a373
W3	Этап 5: логика сохранения	f84d087
Fix	passive_deletes + (недоступно)	abeb191
W31	Toast-уведомления	4d5f2b8
W32	Убраны DEBUG-логи	1b658dc
W38+W39	Trash + предупреждение + фикс shares	59ee6b0
W36	Вкладка «Прикреплено»	9472ce9
W37	Плитки в облаке + прогресс-бар	d8d8ef3
—	Стилизация attached + цвета иконок + порядок модалки	3ca7cc6
15. РЕКОМЕНДАЦИИ ДЛЯ СЛЕДУЮЩЕГО ЧАТА
Приложить этот файл (RESUME_v7.md) + docs/W3.md.

Не смешивать задачи — одна за раз.

Перед боевым — сменить пароли (deploy, PostgreSQL), активировать SSL/сессии.

W34 — тщательная отладка файловых переносов (бэкап перед).

W25 (альбомы) — отдельная большая задача (ТЗ готово отдельно), не смешивать с W34.

16. БАЗОВЫЕ ПРАВИЛА РАБОТЫ
Одно действие — один шаг. Ждать результата.

Не коммитить без проверки (git status / git diff).

Не трогать прод без нужды.

Бэкап БД перед критичными правками.

Комментарии в коде — на русском.

Стиль — рабочий, по делу, с аргументацией.

sed -n 'N,Mp' — только с числами.

Перед патчем — присылать диагностику (sed, grep, journalctl).

Для больших файлов — VS Code, не heredoc.

GitHub-ссылки — только на файлы (tree/ не работает).

Технические правила
После правок шаблонов/Python — sudo systemctl restart framework (или cloud).

check_templates.py — после каждой правки Jinja.

Правки — через Remote-SSH в VS Code.

Локальные копии CDN — обязательно.

sudoers.d — 0440, root:root, финальный \n.

GitHub-токены не хранить, только SSH.

SQLite не используется — только PostgreSQL.

core/config.py — load_dotenv с явным путём к platform/.env.

core_base.html — не base.html (избегаем конфликта).

pip install -e ../core — в venv каждого проекта после клонирования.

FRAMEWORK_TABLES в framework/migrations/env.py — при добавлении новой таблицы в core/models.py добавить её имя в белый список перед flask db migrate.

CSS-конфликты с Bootstrap — избегать имён типа .toast, использовать префиксы (.app-toast-*).

relative_urls: false в TinyMCE — обязательно.

passive_deletes=True в relationship — если FK имеет ondelete='CASCADE', иначе ORM обнуляет FK.

17. ПОЛЕЗНЫЕ КОМАНДЫ
bash
# Перезапуск сервисов
sudo systemctl restart framework cloud
sudo systemctl status framework cloud --no-pager
sudo journalctl -u framework -f

# Бэкап БД
PGPASSWORD='myframework_dev_password' pg_dump -Fc -Z 9 \
  -h localhost -U myframework -d myframework \
  -f ~/backups_platform_$(date +%Y%m%d)/db.dump

# Миграции
cd /home/deploy/apps/platform/framework && source venv/bin/activate
flask db migrate -m "описание"
flask db upgrade
flask db downgrade

# Секреты
python3 -c "import secrets; print(secrets.token_hex(32))"

# Nginx
sudo nginx -t && sudo systemctl reload nginx

# Проверка сервисов
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5002/

# SQL
sudo -u postgres psql myframework
echo 'SELECT * FROM share_attach;' | sudo -u postgres psql myframework
18. ИЗВЕСТНЫЕ ПРОБЛЕМЫ (не критично)
Удаление по иконке в строке облака — не проверяет привязки.

Сессии — browser session (до закрытия браузера). При боевом — PERMANENT_SESSION_LIFETIME.

favicon.ico — 404 на некоторых страницах.

[DEBUG] header_menu_tree — убрано. Если появится — искать print() в context_processor.

19. СЛЕДУЮЩИЙ ШАГ
По выбору:

W34 — делегирование облака.

W40 — подготовка к боевому (HTTPS, сессии).

W33 — утилита ShareAttach.

W35 — закрытая шара.

W25 — рефакторинг альбомов (отдельное ТЗ).

Рекомендация: W34 → W40 → остальные.