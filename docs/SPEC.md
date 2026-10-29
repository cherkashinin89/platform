# SPEC — устройство проекта platform

Актуально на: 2026-10-29.

Единый источник правды по системе: что есть, как устроено, где конфигурируется.
История изменений — docs/HISTORY.md, незакрытые ТЗ — docs/BACKLOG.md, реестр эндпоинтов — docs/routes.md.

---

## 1. Обзор проекта

platform — монорепо из двух ранее отдельных проектов (myframework, mycloud).
Общий пакет core (модели, расширения, авторизация, конфиг, утилиты) используется всеми сервисами.

- **framework** — публичный сайт (статьи, страницы, меню, галерея) + админка + публичные шары (анонимный доступ).
- **cloud** — облачное хранилище: файлы/папки, квоты, шары, Collabora (WOPI), внутреннее API для framework.
- **mail** — веб-интерфейс почты (IMAP через Dovecot): inbox, черновики, поиск, Sieve, вложения из облака.
- **collabora** — Collabora Online (Docker), редактирование/просмотр офисных файлов через WOPI.

---

## 2. Сервисы и порты

Схема: клиент → Nginx → gunicorn (127.0.0.1) → Flask-приложение.

|   Сервис  | Nginx |         gunicorn        |      systemd      |                         Назначение                             |
|-----------|-------|-------------------------|-------------------|----------------------------------------------------------------|
| framework | :80   | 127.0.0.1:5000          | framework.service | сайт, админка, /s/<token>, /files/<id>, /view/<id>, /collabora |
| cloud     | :5001 | 127.0.0.1:5002          | cloud.service     | API облака, /api/*, /wopi/*, internal API                      |
| mail      | :5003 | 127.0.0.1:5004          | mail.service      | веб-почта (IMAP)                                               |
| collabora | :5005 | 127.0.0.1:9980 (Docker) | —                 | Collabora Online (WOPI)                                        |

Инфраструктура: Debian 13 (Trixie), сервер testprod2 (192.168.2.19), Nginx 1.26, Docker (Collabora), WireGuard на роутере. Внешняя флешка BACKUP (/mnt/backup) для бэкапов.

Все юниты — gunicorn, 2 workers, Type=notify, Restart=always.
framework/cloud берут окружение из /home/deploy/apps/platform/.env (EnvironmentFile).

---

## 3. Стек

- Python 3.13.5, Flask 3.0.0, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.2.1, Flask-Migrate 4.0.7, Flask-Caching, Flask-Limiter.
- PostgreSQL 17.11, psycopg[binary] 3.3.6. Миграции — Alembic (единая история в core/migrations, запуск из framework).
- Argon2id (argon2-cffi) — пароли пользователей и шар.
- Nginx (reverse proxy, static, X-Accel-Redirect), gunicorn, systemd.
- Collabora Online (CODE 26.04, Docker, образ collabora/code), WOPI.
- Почта: Postfix 3.10, Dovecot 2.4 (Debian 13), Rspamd 3.12; postfix-pgsql, dovecot-pgsql, dovecot-sieve, dovecot-lmtpd; imapclient в mail.
- Pillow (превью), psutil (статистика), bleach (санитайз HTML в почте), requests (внутренние HTTP framework→cloud/mail), python-dotenv.
- Frontend: Bootstrap 5.3, Bootstrap Icons 1.11, TinyMCE 7, Sortable.js 1.15 — всё локально, vanilla JS.

---

## 4. Пакет core

Общий код для framework/cloud/mail:

- **models.py** — все SQLAlchemy-модели (единая схема БД).
- **extensions.py** — db, login_manager, csrf, migrate (общие экземпляры).
- **config.py** — CoreConfig, загрузка .env (load_dotenv из корня platform), общие пути и ключи.
- **auth.py** — декораторы ролей: admin_required, editor_required, user_required, role_required.
- **cloud_utils.py** — доступ к файлам облака, шары, пути, list_folder_items, get_share_by_token.
- **file_utils.py / image_utils.py / files_icons.py** — типы файлов, MIME, превью, иконки, размеры.
- **content_service.py** — регистрация/снятие использования файлов (FileUsage) для статей/страниц/альбомов.
- **system_stats.py, backup_utils.py, slug_utils.py** — статистика, бэкапы, слаги.


---

## 5. Модели

Все модели — в core/models.py (единая схема для всех сервисов). Ниже — ключевые поля; полные определения см. в коде.

### 5.1. Пользователи

- **User** — username, full_name, email, password_hash (Argon2id с префиксом {ARGON2ID} для Dovecot), role (viewer/user/editor/admin), quota_bytes, mail_quota_bytes.
  Иерархия ролей: viewer < user < editor < admin. M2M со статьями (авторы).

### 5.2. Контент и медиа

- **Article** — title, content, summary, is_published, archived_at (W3).
- **Page** — title, slug (unique), content.
- **MenuItem** — title, url, order, position (header/sidebar/footer), parent_id, page_id (one-to-one со страницей).
- **UploadedFile** — системные файлы (лого, favicon): original_name, stored_name, mime_type, file_type, size, thumbnail_name.
- **Album** — title, slug, cover_photo_id, is_published, order; M2M со статьями.
- **Photo** — album_id, file_id (CloudFile), caption, order, is_featured (слайдер шапки).
- **SiteSettings** — синглтон: site_title/subtitle/description/keywords; base_url сайта/облака/почты/collabora; показ header/sidebar/footer; тема; лого/favicon; слайдер; архивация статей (W3).

### 5.3. Облако

- **CloudFile** — owner_id, parent_id, name, is_folder, stored_name, size, mime_type, is_trashed, trashed_at. Дерево папок (children).
- **CloudShare** — token (unique), file_id, created_by_id, expires_at, password_hash, download_count, max_downloads, can_edit (W48), is_public (W35). Методы is_expired, set_password/check_password.
- **ContentFile** (W58) — file_id, target_type (article/page), target_id. Замена ShareAttach; unique (file_id, target_type, target_id).
- **WopiToken** (W48) — token, file_id, user_id, share_id, can_write, expires_at. Токен доступа Collabora.
- **CloudFileVersion** (W48) — file_id, stored_name, size, created_by_id, created_at. История версий файла.

### 5.4. Почта

- **MailDomain** — name (unique), is_active.
- **Mailbox** — user_id, domain_id, local_part, password_hash (Dovecot SHA512-CRYPT), name, quota_bytes, is_active, last_login. unique (domain_id, local_part).
- **MailUiState** (W47) — user_id (unique), sort, dir, filters (JSON), per_page.
- **MailSettings** (W47) — user_id (unique), signature, signature_html.
- **RecentRecipient** (W47) — user_id, email, name, last_used, use_count. unique (user_id, email).
- **SieveRule** (W47) — user_id, name, is_active, priority, conditions (JSON), actions (JSON).

### 5.5. Реестры и аудит

- **FileUsage** (W3) — file_id, entity_type (article/page/album/photo), entity_id, user_id. Реестр использования облачных файлов.
- **AuditLog** — user_id, action, target_type, target_id, details (JSON). Журнал значимых действий.

---

## 6. API-обзор

Полный реестр эндпоинтов — docs/routes.md (генерируется deploy/gen_routes.py: методы, пути, endpoint, категория public/auth/admin/internal/wopi, назначение, файл:функция). Ниже — группы.

### 6.1. framework

- Публичная часть: / (главная), /articles, /article/<id>, /page/<slug>, /gallery, /search.
- Аутентификация: /login, /logout, /whoami.
- Админка: /admin/* (статьи, страницы, меню, файлы, альбомы, настройки, пользователи, бэкапы).
- Шары и файлы: /s/<token> (просмотр), /s/<token>/auth (пароль, W35), /s/<token>/download[/<file_id>], /files/<id> (X-Accel), /view/<id> (read-only, W59), /collabora (редактор).
- Служебное: /uploads/, /attached, /media, /shares.

### 6.2. cloud

- API облака: /api/* (файлы/папки, загрузка, перемещение, корзина, шары, квоты).
- Шары (публичное): /s/<token>.
- WOPI: /wopi/files/<id>[/contents] (CheckFileInfo/GetFile/PutFile), /api/wopi-token/<id>.
- Internal API: /api/internal-share/<file_id> (X-Internal-Key, от framework — прикрепление файлов к статьям).

### 6.3. mail

- Страницы: /, /inbox, /folder/<name>, /message/<uid>, /settings, /settings/rules.
- API: /api/message/<uid>, /api/attachment/<uid>/<index>, /api/draft[/delete|/latest-draft], /api/search, /api/folder/*, /api/message/{trash,move}, /api/unread-count, /api/latest-unread, /api/recipients, /api/cloud-* (вложения из облака), /api/share-file/<id>, /api/sieve/*, /health.

---

## 7. Конфигурация

### 7.1. Переменные окружения (.env)

Файл /home/deploy/apps/platform/.env, права 600. Загружается в core/config.py (load_dotenv из корня platform); systemd также подхватывает его через EnvironmentFile (framework, cloud).

| Переменная                                    | Назначение                                                       |
|-----------------------------------------------|------------------------------------------------------------------|
| SECRET_KEY                                    | Секрет Flask-сессий (общий для SSO между сервисами)              |
| DATABASE_URL                                  | PostgreSQL DSN                                                   |
| CLOUD_DATA_ROOT                               | Корень файлов облака (alias CLOUD_DATA_DIR в cloud)              |
| INTERNAL_API_KEY                              | Общий секрет framework↔cloud (X-Internal-Key)                    |
| MAIL_INTERNAL_URL                             | Внутренний URL mail-сервиса (по умолчанию http://127.0.0.1:5004) |
| MAIL_DOMAIN, MAIL_HOSTNAME                    | Домен/хост почты                                                 |
| MAIL_DB_USER, MAIL_DB_PASSWORD, MAIL_DB_NAME  | Доступ к почтовой БД (Dovecot/Postfix)                           |
| MAIL_MASTER_PASSWORD                          | Master-пароль Dovecot                                            |
| VMAIL_HOME, VMAIL_UID, VMAIL_GID              | Путь и владелец виртуальной почты                                |
| EXTERNAL_BACKUP_PATH                          | Каталог внешних бэкапов (по умолчанию /mnt/backup)               |

### 7.2. SiteSettings (БД)

Синглтон SiteSettings хранит настройки, изменяемые из админки: название/описание/ключевые слова сайта; base_url для сайта, облака, почты, Collabora (collabora_base_url — без хардкода в коде); показ header/sidebar/footer; активная тема; лого и favicon (UploadedFile); слайдер (до 10 is_featured фото); архивация статей.

### 7.3. Nginx

- framework.conf: :80 → 5000; /static/shared/ → core/static/; /static/ → framework/static/; /uploads/ → framework/uploads/; /protected_files/ (internal) → cloud/cloud_data/.
- cloud.conf: :5001 → 5002; статика cloud и shared.
- collabora.conf: :5005 → 9980 (/browser, /hosting/, /cool/); WebSocket.

Примечание: локация /protected_files/ (W58) есть в системном /etc/nginx/sites-available/framework, но отсутствует в deploy/nginx/framework.conf в репо (см. POLISH P1).

### 7.4. systemd

framework.service, cloud.service, mail.service — gunicorn (2 workers), Type=notify, Restart=always. framework/cloud — User=deploy, EnvironmentFile=.env; mail — PATH с venv.

---

## 8. Деплой

Скрипт: deploy/setup.sh (Debian 12/13, пользователь deploy с sudo).

Порядок:

1. Проверки: наличие .env, папок core/framework/cloud.
2. Системные пакеты: python3/venv/pip/dev, nginx, git, acl, libffi/libssl, build-essential, docker.io/docker-compose.
3. ACL для Nginx (setfacl -m g:www-data:x /home/deploy).
4. venv для framework и cloud; pip install -r requirements.txt; pip install -e core.
5. Миграции (из framework): flask db upgrade; flask create-admin.
6. Nginx: копирование framework/cloud/collabora.conf в sites-available/enabled, nginx -t, reload.
7. Collabora: docker compose up -d (collabora/docker-compose.yml).
8. systemd: подстановка __SERVICE_USER__, enable/restart framework и cloud.
9. sudoers: файлы из deploy/sudoers/ с подстановкой пользователя (chmod 0440).

Запуск: cp deploy/env.example .env; nano .env; chmod 600 .env; sudo SERVICE_USER=deploy bash deploy/setup.sh.

Бэкап БД перед критичными правками: pg_dump "$DATABASE_URL" -Fc -f ~/backups/platform_<ts>.dump (см. docs/README.md).

---

## 9. Безопасность

- **SSO между сервисами**: общий SECRET_KEY и SESSION_COOKIE_NAME=session; куки HttpOnly, SameSite=Lax (Secure/Domain — при переходе на HTTPS, W40).
- **Роли**: viewer < user < editor < admin; декораторы core/auth.py (admin_required, editor_required, user_required, role_required) с @wraps.
- **CSRF**: Flask-WTF, токен во всех POST-формах и API (X-CSRFToken); служебный internal API cloud — @csrf.exempt с проверкой X-Internal-Key.
- **Пароли**: Argon2id (argon2-cffi). User — с префиксом {ARGON2ID} (Dovecot); CloudShare — без префикса. Mailbox — SHA512-CRYPT (Dovecot).
- **Облачные файлы**: X-Accel-Redirect (/protected_files/ internal) — Nginx отдаёт файл, Python не стримит. /files/<id> — с проверкой прав/публичности (W58).
- **Шары (W35)**: is_public (аноним/только логин), пароль (Argon2id, сессия share_access_<token>), expires_at, max_downloads + download_count; get_share_by_token отсекает истёкшие/исчерпанные; файл в корзине — недоступен (W38).
- **Internal API**: X-Internal-Key (INTERNAL_API_KEY) + X-User-Id; используется framework для прикрепления файлов к статьям.
- **WOPI (W48)**: WopiToken с expires_at, can_write; доступ Collabora к файлам только по токену.

---

## 10. Миграции

Alembic + Flask-Migrate. Единая история — core/migrations/ (до реорганизации миграции велись в каждом сервисе отдельно; теперь общие).

- Запуск — из venv framework (Migrate инициализирован с directory=core/migrations).
- Генерация: flask db revision --autogenerate -m "описание".
- Применение: flask db upgrade.
- Утилита учтена в setup.sh (шаг 5).

Текущие ревизии (8): 761def80153f (initial) → 443460781cdd (WOPI) → 5fb1dec6057c (can_edit) → 85a8e1d783c2 (CloudFileVersion) → 759237a42d1e (ContentFile) → e4232b9afd1c (collabora_base_url) → 616fd1a65e3f (is_public). Head: 616fd1a65e3f.

---

## 11. Структура репозитория


