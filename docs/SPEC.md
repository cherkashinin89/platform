# SPEC — единый источник правды по проекту platform

**Версия:** v7 (после ревизии)
**Дата:** 2026-10-28
**Статус:** W58 (X-Accel-Redirect) — завершён. W59 (просмотр офисных файлов read-only) — завершён. W48 (Collabora) — v1. W35 (закрытая шара) — следующий шаг.

## 0. КАК ЧИТАТЬ ЭТОТ ФАЙЛ

- Это **единый источник правды** по проекту.
- **Все** задачи — здесь.
- **Все** реализованные фичи — здесь.
- **При старте нового чата** — сообщить ассистенту **ссылку на этот файл** (raw.githubusercontent.com/cherkashinin89/platform/refs/heads/main/docs/SPEC.md).
- **Обновлять** после **каждой** задачи.

### Работа с детальными ТЗ (docs/tasks/)

- **Большие задачи** (W48, W59 и т.п.) имеют **детальное ТЗ** в `docs/tasks/W<номер>.md`.
- В SPEC (раздел 7) — **краткое описание** (цель, статус, оценка) + **ссылка** на файл ТЗ.
- При старте работы над задачей — **открыть `docs/tasks/W<номер>.md`** (там полное описание, шаги, нюансы).
- После завершения задачи — **обновить** и SPEC (кратко), и `docs/tasks/W<номер>.md` (детали).
- **Не дублировать** детали: SPEC — «что и зачем», `tasks/` — «как именно».

**Пример:**
- SPEC, раздел 7.12: «W48 — Collabora. Цель: … Статус: v1. Детали: `docs/tasks/W48.md`».
- `docs/tasks/W48.md`: полное ТЗ (этапы, код, WOPI, история версий, ошибки).

## 1. ОБЩАЯ ИНФОРМАЦИЯ

### 1.1. Стек

**Backend:**
- Python 3.13.5
- Flask 3.0.0, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3, Flask-WTF 1.2.1, Flask-Migrate 4.0.7
- PostgreSQL 17.11 + psycopg[binary]==3.3.6
- **argon2-cffi** (единый хэшер паролей для framework/cloud/mail)
- Pillow 11.3.0 / 12.3.0, psutil 5.9.8, python-dotenv 1.0.1, email_validator 2.1.1
- requests 2.x (внутренние HTTP framework → cloud, framework → mail)
- gunicorn 21.2.0

**Frontend:**
- Bootstrap 5.3.0, Bootstrap Icons 1.11.0, TinyMCE 7, Sortable.js 1.15.2 — всё локально.
- Vanilla JS.

**Почта:**
- Postfix 3.10.13
- Dovecot 2.4.1-4 (Debian 13 Trixie) — **см. раздел 9 (известные проблемы)**
- Rspamd 3.12.1
- Postfix-pgsql, dovecot-pgsql, dovecot-sieve, dovecot-lmtpd

**Collabora (W48/W59):**
- Collabora Online Development Edition (CODE) 26.04.5.2, Docker-контейнер.
- Nginx reverse proxy (`:5005` → `127.0.0.1:9980`).
- WOPI-интеграция (CheckFileInfo, GetFile, PutFile, PutRelativeFile — отключён).

### 1.2. Инфраструктура

- **Сервер:** RV511 (i3 M380, 6 ГБ RAM, HDD 1 ТБ), Debian 13 Trixie x86_64, хостнейм `testprod2`.
- **IP:** 192.168.2.19, юзер `deploy`.
- **Монорепо:** `/home/deploy/apps/platform/`
- **Nginx 1.26.3 (reverse proxy):**
  - `:80` → `127.0.0.1:5000` (framework)
  - `:5001` → `127.0.0.1:5002` (cloud)
  - `:5003` → `127.0.0.1:5004` (mail)
  - `:5005` → `127.0.0.1:9980` (Collabora)
  - `/protected_files/` → `internal` alias на `cloud_data/` (X-Accel-Redirect, W58)
- **Gunicorn:** 2 воркера на каждом сервисе.
- **systemd:** `framework.service`, `cloud.service`, `mail.service`.
- **Docker:** `collabora` (docker-compose.yml в `collabora/`).
- **WireGuard** на роутере TP-Link Archer AX55.
- **Внешняя флешка BACKUP** (exfat, UUID FFBB-A34E, 3.8 ГБ) — `/mnt/backup`.

### 1.3. Реквизиты (тестовые, сменить при боевом)

- Админка: `admin / admin123` (создан через `flask create-admin`)
- Пароль `deploy` (SSH/sudo): `Zxfg5h!!.`
- Пароль PostgreSQL (`myframework`): `myframework_dev_password`
- БД: `myframework`, юзер: `myframework`
- Пользователь БД для почты: `mail_reader`, пароль: `mail_reader_dev_password`
- `SECRET_KEY=358b1c3dc829c638f2111058148bfd70760650e783d9c136580e2c45cf5691f1`
- `INTERNAL_API_KEY=a510093a20099456fdfcc1effb6ff15285fb4b49bfcb517fab4580de1405c003`

### 1.4. Переменные `.env` (почта + Collabora)
MAIL_HOSTNAME=testprod2
MAIL_DOMAIN=testprod2.local
MAIL_DB_USER=mail_reader
MAIL_DB_PASSWORD=mail_reader_dev_password
MAIL_DB_NAME=myframework
VMAIL_UID=5000
VMAIL_GID=5000
VMAIL_HOME=/var/vmail
MAIL_INTERNAL_URL=http://127.0.0.1:5004

# W47: master-user Dovecot
MAIL_MASTER_PASSWORD=<секрет>

text

## 2. СТРУКТУРА МОНОРЕПО (АКТУАЛЬНАЯ)
/home/deploy/apps/platform/ ← git: github.com/cherkashinin89/platform
├── README.md
├── .gitignore
├── .env ← ОДИН общий
│
├── core/ ← общий пакет (pip install -e ../core)
│ ├── __init__.py
│ ├── pyproject.toml
│ ├── models.py ← User, Article, Page, …, CloudFile, CloudShare, ContentFile,
│ │ WopiToken, CloudFileVersion, MailDomain, Mailbox
│ ├── extensions.py
│ ├── auth.py
│ ├── config.py ← CoreConfig
│ ├── cloud_utils.py
│ ├── content_service.py
│ ├── file_utils.py
│ ├── image_utils.py
│ ├── slug_utils.py
│ ├── system_stats.py
│ ├── backup_utils.py
│ ├── files_icons.py
│ ├── migrations/ ← ЕДИНСТВЕННЫЙ источник правды по схеме БД
│ │ ├── env.py
│ │ ├── alembic.ini
│ │ ├── script.py.mako
│ │ └── versions/ (initial + wopi_token + cloud_file_version + content_file + collabora_base_url)
│ ├── templates/ (core_base.html, partials/)
│ └── static/ (css, js, vendor)
│
├── framework/ ← сайт + админка
│ ├── app.py (create_app + все маршруты)
│ ├── cli.py (flask create-admin)
│ ├── config.py
│ ├── forms.py
│ ├── mail_utils.py
│ ├── search_service.py
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── venv/
│ ├── uploads/
│ ├── archives/
│ ├── templates/ (base.html, article.html, …)
│ └── static/ (tinymce, sortable)
│
├── cloud/ ← облако
│ ├── app.py (create_app + маршруты)
│ ├── wopi.py (WOPI-эндпоинты, W48/W58)
│ ├── cloud_service.py
│ ├── config.py
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── venv/
│ ├── cloud_data/ (физические файлы; НЕ в git)
│ ├── templates/ (base_cloud.html, index.html, shares.html, attached.html, …)
│ └── static/css/cloud.css
│
├── mail/ ← почта
│ ├── app.py
│ ├── config.py
│ ├── mail_service.py
│ ├── imap_client.py
│ ├── wsgi.py
│ ├── static/css/mail.css, static/js/{mail.js, compose.js}
│ ├── requirements.txt
│ ├── venv/
│ ├── templates/ (base_mail.html, index.html, …)
│ └── static/vendor/tinymce/
│
├── collabora/ ← Collabora Online (Docker)
│ └── docker-compose.yml
│
├── docs/
│ ├── SPEC.md ← ЭТОТ ФАЙЛ
│ └── tasks/ (W48.md, W59.md, …)
│
└── deploy/
├── README.md
├── setup.sh
├── setup-mail.sh
├── env.example
├── nginx/{framework,cloud,mail,collabora}.conf
├── systemd/{framework,cloud,mail}.service
├── sudoers/{framework-restart,framework-mount,cloud-restart,mail-restart}
└── templates/ (postfix, dovecot, rspamd)

text

## 3. МОДЕЛИ (core/models.py) — КРАТКО

### 3.1. Контент и пользователи
- **User** — `id`, `username`, `email` (nullable), `password_hash` (Argon2id), `role`, `quota_bytes`, `mail_quota_bytes`.
- **Article** — `is_published` (Boolean), `slug`, `content` (HTML).
- **Page** — `title`, `slug`, `content` (всегда публична, поля `is_published` нет).
- **MenuItem**, **UploadedFile**, **Album**, **Photo**.
- **SiteSettings** — `site_base_url`, `cloud_base_url`, `mail_base_url`, **`collabora_base_url`** (W59).

### 3.2. Облако (W48/W58)
- **CloudFile** — `owner_id`, `parent_id`, `is_folder`, `stored_name`, `size`, `mime_type`, `is_trashed`.
- **CloudShare** — `token`, `file_id`, `created_by_id`, `expires_at`, `password_hash`, `download_count`, `max_downloads`, **`can_edit`** (W48), `is_public` (W35).
- **ContentFile** (W58) — `file_id`, `target_type` (`article`/`page`), `target_id`. **Замена `ShareAttach`**.
- **WopiToken** (W48) — `token`, `file_id`, `user_id`, `share_id`, `can_write`, `expires_at`.
- **CloudFileVersion** (W48) — `file_id`, `stored_name`, `size`, `created_by`, `created_at`.

### 3.3. Почта (W2)
- **MailDomain**, **Mailbox**, **MailUiState**, **MailSettings**, **RecentRecipient**, **SieveRule**.

## 4. АРХИТЕКТУРА

### 4.1. Единая история миграций (W58)
- **`core/migrations/`** — единственный источник правды.
- `env.py` — без белого списка, все модели из `core.models`.
- `version_table='alembic_version'` (одна).
- framework/cloud/mail **не имеют** своих `migrations/`.
- История до перехода — в git-коммитах до `0d5cca0`.

### 4.2. SSO (единый вход)
- Cookie `session` (Domain=`192.168.2.19`), `SECRET_KEY` общий.
- Framework — форма логина. Cloud/mail — читают сессию.
- **Проблема:** `SameSite=Lax` может блокировать cross-port XHR (см. W40 — HTTPS).

### 4.3. Единый пароль (Argon2id)
- `User.set_password` — Argon2id + префикс `{ARGON2ID}`.
- Dovecot читает `User.password_hash` (SQL).

### 4.4. Прикрепление файлов (W58 — X-Accel-Redirect)
- Файлы в `cloud_data/<owner_id>/<stored_name>` — **не доступны напрямую**.
- В статьях/страницах — ссылки `/files/<id>` (framework).
- `/files/<id>` проверяет `ContentFile` (привязка к опубликованной статье/странице), возвращает `X-Accel-Redirect` → Nginx отдаёт файл.
- Nginx: `location /protected_files/ { internal; alias .../cloud_data/; }`.

### 4.5. Collabora (W48/W59)
- **WOPI:** `CheckFileInfo`/`GetFile`/`PutFile` (в `cloud/wopi.py`).
- **Токены:** `WopiToken` (TTL 1 час, продление при активности).
- **Редактирование:** `/collabora` (облако, iframe на весь экран).
- **Просмотр:** `/view/<file_id>` (framework, JSON) → модалка (read-only, `file-viewer.js`).
- **URL:** из `SiteSettings.collabora_base_url` / `cloud_base_url` (без хардкода).

## 5. РЕАЛИЗОВАНО (КРАТКО)

- **W3** — прикрепление файлов (устарело, заменено W58).
- **W31** — toast-уведомления.
- **W2** — почта (Postfix, Dovecot, Rspamd, mail-сервис, админка).
- **W47** — UI почты (Этапы 1–7 + A/B/C/D, полировка).
- **W48** — Collabora (v1): docx/xlsx/pptx, `can_edit`, история версий, `/collabora`.
- **W58** — X-Accel-Redirect: `ContentFile`, `/files/<id>`, `/protected_files/`, удалён `ShareAttach`.
- **W59** — просмотр офисных файлов (read-only, модалка `/view/<id>`).

## 6. В РАБОТЕ
- **W35** — закрытая шара (пароль, срок, лимит). Детали: `docs/tasks/W35.md`. **Следующий шаг.**

## 7. ЗАПЛАНИРОВАНО (СОКРАЩЁННО)

- **W40** — подготовка к боевому (HTTPS, поддомены, сессии, смена паролей).
- **W41** — асинхронные операции (удаление пользователя).
- **W42** — чистка мусора.
- **W43** — альтернатива Dovecot (Stalwart).
- **W44** — мониторинг Dovecot 2.4.
- **W45** — удалить `Mailbox.password_hash`.
- **W25** — рефакторинг альбомов.
- **W56** — система ошибок (ErrorLog, `/admin/errors/`) — доработать ТЗ.
- **W33** — ShareAttach-утилита (устарело).
- **W15** — бэкап почты.
- **W48** — UI соавторов (отложено).

## 8. ИДЕИ
- X1. Блочный редактор (вместо TinyMCE).
- X2. Криптопровайдер (ЭЦП).

## 9. ИЗВЕСТНЫЕ БАГИ (СОКРАЩЁННО)

- БАГ-W2-001 — вёрстка `user_delete_modal.html`.
- БАГ-W2-005 — карточки на `/admin/quotas/user/<id>`.
- БАГ-W2-006 — кэш браузера на `/admin/quotas/`.
- Удаление файла в облаке не проверяет привязки (средний).
- favicon.ico — 404.
- **БАГ-W47-DOVECOT-*** (master-user, passdb, prefetch, права) — **решены**.
- **БАГ-W47-SUBJECT-001**, **ENCODING-001**, **THREAD-001**, **MAILBOX-001**, **DUPLICATE-001**, **TEMPLATE-001**, **JINJA-001** — **решены**.

## 10. КОСМЕТИКА
- Toast в правый нижний угол (низкий).

## 11. ПРАВИЛА РАБОТЫ
- Один шаг — одно действие. Ждать результата.
- Не коммитить без проверки.
- Бэкап БД перед критичными правками.
- Комментарии — на русском.
- После правок шаблонов/Python — `systemctl restart framework/cloud/mail`.
- Миграции — только в `core/migrations/`.
- `core_base.html` — не `base.html`.
- `pip install -e ../core` — в venv каждого проекта.
- Пароли: Argon2id, префикс `{ARGON2ID}`.

## 12. ПОЛЕЗНЫЕ КОМАНДЫ
(без изменений)

## 13. ИСТОРИЯ КОММИТОВ (КРАТКО)

(ключевые: W48, W58, W59, `0d5cca0` — миграции, `49a7c52` — финал)

## 14. СЛЕДУЮЩИЙ ШАГ

**Текущая задача: W35 — закрытая шара.**
W58/W59 завершены. W35 — пароль, срок, лимит (модель `CloudShare` готова).

Рекомендация: W35 → W40 (HTTPS) → W41 (асинхронные) → W56 (ошибки).