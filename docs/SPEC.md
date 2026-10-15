markdown
# SPEC — единый источник правды по проекту platform

**Версия:** v1
**Дата:** 2026-10-14
**Статус:** W2 (почта) завершён, идёт подготовка к W40 (боевой)

---

## 0. КАК ЧИТАТЬ ЭТОТ ФАЙЛ

- Это **единый источник правды** по проекту.
- **Все** задачи — здесь.
- **Все** реализованные фичи — здесь.
- **При старте нового чата** — сообщить ассистенту **ссылку на этот файл** (raw.githubusercontent.com/cherkashinin89/platform/refs/heads/main/docs/SPEC.md).
- **Детальные ТЗ** по **большим** задачам — в `docs/tasks/W*.md`.
- **Обновлять** после **каждой** задачи.

---

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
- Dovecot 2.4.1-4 (Debian 13 Trixie) — **см. раздел 10 (известные проблемы)**
- Rspamd 3.12.1
- Postfix-pgsql, dovecot-pgsql, dovecot-sieve, dovecot-lmtpd

### 1.2. Инфраструктура

- **Сервер:** RV511 (i3 M380, 6 ГБ RAM, HDD 1 ТБ), Debian 13 Trixie x86_64, хостнейм `testprod2`.
- **IP:** 192.168.2.19, юзер `deploy`.
- **Монорепо:** `/home/deploy/apps/platform/`
- **Nginx 1.26.3 (reverse proxy):**
  - `:80` → `127.0.0.1:5000` (framework)
  - `:5001` → `127.0.0.1:5002` (cloud)
  - `:5003` → `127.0.0.1:5004` (mail)
- **Gunicorn:** 2 воркера на каждом сервисе.
- **systemd:** `framework.service`, `cloud.service`, `mail.service` (в `/etc/systemd/system/`).
- **WireGuard** на роутере TP-Link Archer AX55.
- **Внешняя флешка BACKUP** (exfat, UUID FFBB-A34E, 3.8 ГБ) — `/mnt/backup`.

### 1.3. Реквизиты (тестовые, сменить при боевом)

- Админка: `admin / admin123`
- Пароль `deploy` (SSH/sudo): `Zxfg5h!!.`
- Пароль PostgreSQL (`myframework`): `myframework_dev_password`
- БД: `myframework`, юзер: `myframework`
- Пользователь БД для почты: `mail_reader`, пароль: `mail_reader_dev_password`
- `SECRET_KEY=358b1c3dc829c638f2111058148bfd70760650e783d9c136580e2c45cf5691f1`
- `INTERNAL_API_KEY=a510093a20099456fdfcc1effb6ff15285fb4b49bfcb517fab4580de1405c003`

### 1.4. Переменные `.env` (почта)
MAIL_HOSTNAME=testprod2
MAIL_DOMAIN=testprod2.local
MAIL_DB_USER=mail_reader
MAIL_DB_PASSWORD=mail_reader_dev_password
MAIL_DB_NAME=myframework
VMAIL_UID=5000
VMAIL_GID=5000
VMAIL_HOME=/var/vmail
MAIL_INTERNAL_URL=http://127.0.0.1:5004

text

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
│ ├── models.py ← User, Article, Page, …, MailDomain, Mailbox
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
│ ├── templates/
│ │ ├── core_base.html
│ │ └── partials/
│ │ ├── header.html
│ │ ├── file_manager_modal.html
│ │ ├── attached_file.html
│ │ ├── folder_view.html
│ │ └── ...
│ └── static/
│ ├── css/style.css
│ ├── themes/{default,dark}/style.css
│ ├── js/
│ │ ├── attached-files.js
│ │ └── toast.js
│ └── vendor/{bootstrap,bootstrap-icons}/
│
├── framework/ ← сайт + админка
│ ├── app.py
│ ├── config.py
│ ├── forms.py
│ ├── mail_utils.py ← HTTP к mail (hash-password, quota, reload, archive)
│ ├── search_service.py
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── migrations/versions/
│ │ ├── def34305bcda_initial_schema_postgresql_baseline.py
│ │ ├── bec349bf7b84_w3_file_usage_audit_log_archive_.py
│ │ ├── b3fce6fbe4b6_w3_photo_file_id_cloud_file_id.py
│ │ ├── 9f246cb32d6e_w3_share_attach.py
│ │ ├── 5a8e2fd60c6b_add_user_mail_quota_bytes.py
│ │ └── e3eb7555661a_user_email_nullable.py
│ ├── venv/
│ ├── uploads/
│ ├── archives/
│ ├── templates/
│ │ ├── base.html
│ │ ├── article.html, page.html, index.html, articles_list.html, search.html, login.html
│ │ ├── public_share.html, public_share_invalid.html
│ │ ├── _pagination.html
│ │ ├── partials/
│ │ │ ├── folder_view.html
│ │ │ ├── attached_file.html
│ │ │ ├── articles_grid.html
│ │ │ ├── _menu_macros.html
│ │ │ └── recent_articles.html
│ │ ├── gallery/{index,album}.html
│ │ └── admin/
│ │ ├── base_admin.html
│ │ ├── article_form.html, page_form.html
│ │ ├── users.html, user_form.html, user_delete_modal.html
│ │ ├── settings.html (с блоком «Почтовые домены»)
│ │ ├── files.html, albums.html, album_form.html
│ │ ├── quotas.html ← /admin/quotas/
│ │ ├── quota_user.html ← детали пользователя
│ │ └── mail/
│ │ ├── domains.html
│ │ ├── domain_form.html
│ │ ├── mailboxes.html
│ │ └── mailbox_form.html
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
│ │ ├── index.html
│ │ ├── shares.html
│ │ ├── attached.html
│ │ ├── trash.html
│ │ └── public_share.html, public_share_invalid.html
│ └── static/css/cloud.css
│
├── mail/ ← почта (Flask-сервис)
│ ├── app.py
│ ├── config.py
│ ├── mail_service.py ← doveadm, systemctl, archive
│ ├── wsgi.py
│ ├── requirements.txt
│ ├── venv/
│ ├── migrations/
│ │ ├── env.py
│ │ ├── alembic.ini
│ │ ├── script.py.mako
│ │ └── versions/
│ │ └── 2d9755b81350_initial_mail_schema_mail_domain_mailbox.py
│ └── templates/
│ ├── base.html
│ ├── index.html ← главная (карточка ящика)
│ └── change_password.html
│
├── docs/
│ ├── SPEC.md ← ЭТОТ ФАЙЛ (единый источник правды)
│ └── tasks/
│ └── W3.md ← детальное ТЗ W3
│
└── deploy/
├── README.md
├── setup.sh ← framework + cloud
├── setup-mail.sh ← почта
├── env.example
├── nginx/{framework,cloud,mail}.conf
├── systemd/{framework,cloud,mail}.service
├── sudoers/{framework-restart,framework-mount,cloud-restart,mail-restart}
└── templates/
├── postfix/
│ ├── main.cf
│ ├── pgsql-virtual-mailbox-domains.cf
│ └── pgsql-virtual-mailbox-maps.cf
├── dovecot/
│ ├── 10-auth.conf
│ ├── 10-mail.conf
│ ├── 10-master.conf
│ ├── 10-ssl.conf
│ ├── 20-lmtp.conf
│ ├── 90-quota.conf
│ ├── auth-sql.conf.ext
│ └── dovecot.conf
└── rspamd/
├── dkim_signing.conf
└── milter_headers.conf

text

---

## 3. МОДЕЛИ (core/models.py)

### 3.1. Контент и пользователи

- **User** — `id`, `username` (unique), `full_name`, `email` (nullable, unique), `password_hash` (**Argon2id** с префиксом `{ARGON2ID}`), `role` (viewer/user/editor/admin), `created_at`, `quota_bytes` (облако), `mail_quota_bytes` (почта, дефолт для новых ящиков).
- **Article**, **Page**, **MenuItem**, **UploadedFile** — без изменений.
- **Album**, **Photo** — без изменений (W25 — рефакторинг в плане).
- **SiteSettings** — `mail_base_url`, `cloud_base_url`, `site_base_url` и т.д.

### 3.2. Облако

- **CloudFile** — `owner_id`, `parent_id`, `is_folder`, `stored_name`, `size`, `mime_type`, `is_trashed`, `trashed_at`.
- **CloudShare** — `token`, `file_id`, `created_by_id`, `expires_at`, `password_hash`, `download_count`, `max_downloads`.
- **ShareAttach** (W3) — `share_id`, `target_type` (article/page), `target_id`.

### 3.3. Аудит и использование

- **FileUsage**, **AuditLog**.

### 3.4. Почта (W2)

**MailDomain:**
```python
class MailDomain(db.Model):
    __tablename__ = 'mail_domain'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
Mailbox:

python
class Mailbox(db.Model):
    __tablename__ = 'mailbox'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('mail_domain.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    local_part = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # legacy, не используется
    name = db.Column(db.String(255), nullable=True)
    quota_bytes = db.Column(db.BigInteger, nullable=False,
                            default=1024 * 1024 * 1024)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('domain_id', 'local_part', name='uq_mailbox_domain_local'),
    )

    @property
    def email(self):
        return f'{self.local_part}@{self.domain.name}'
ВАЖНО: Mailbox.password_hash — legacy. Авторизация идёт через User.password_hash (Argon2id). Поле остаётся в БД, но не используется (можно удалить в будущем — см. W45 в разделе 7).

MailAlias — НЕ создаём. Ролевые адреса — через пользователей. Если понадобится — отдельная задача.

4. АРХИТЕКТУРА
4.1. Три сервиса — одна БД, разные истории миграций
Общая БД: myframework.

Свои истории миграций:

framework/migrations/ → alembic_version, FRAMEWORK_TABLES.

cloud/migrations/ → alembic_version_cloud, свой белый список.

mail/migrations/ → alembic_version_mail, MAIL_TABLES = {mail_domain, mailbox, alembic_version_mail}.

Модели — в core/models.py (общий источник правды).

4.2. SSO (единый вход)
На тестовом: разные origin (:80, :5001, :5003). Cookie session — Domain=192.168.2.19 (без порта) — шарятся между портами. SSO работает.

На боевом: поддомены (site.ru, cloud.site.ru, mail.site.ru). Cookie .site.ru. SSO работает.

4.3. Единый пароль (Argon2id)
User.set_password — Argon2id с префиксом {ARGON2ID}.

User.check_password — убирает префикс, проверяет через argon2-cffi.

Dovecot — читает password_hash из "user" (SQL). Префикс {ARGON2ID} — сам определяет схему.

Werkzeug — не используется.

4.4. Квоты
Облако: User.quota_bytes. Проверяется в framework/cloud.

Почта: Mailbox.quota_bytes. Проверяется Dovecot.

Отображение: /admin/quotas/ — обе квоты рядом.

Управление: /admin/quotas/user/<id> — карточки облака + секция «Почтовые ящики».

4.5. Доступ framework ↔ mail
Прямой через БД: MailDomain, Mailbox — framework читает/пишет напрямую.

HTTP (внутренний API): mail_utils.py:

hash_password(password) → POST /api/internal/hash-password

get_quota(email) → GET /api/internal/quota/<email>

reload_service(name) → POST /api/internal/reload/<service>

archive_mailbox(email) → POST /api/internal/archive-mailbox/<email>

Авторизация: X-Internal-Key: INTERNAL_API_KEY.

4.6. Внутренний API mail
Метод	Путь	Назначение
POST	/api/internal/hash-password	Генерация {SHA512-CRYPT} (legacy) — теперь не используется
GET	/api/internal/quota/<email>	doveadm quota get
POST	/api/internal/reload/<service>	systemctl reload postfix/dovecot/rspamd
POST	/api/internal/archive-mailbox/<email>	Архивация Maildir в /tmp/
4.7. Dovecot SQL-аутентификация
/etc/dovecot/conf.d/auth-sql.conf.ext:

text
pgsql 127.0.0.1 {
  parameters {
    user = mail_reader
    password = mail_reader_dev_password
    dbname = myframework
  }
}

passdb sql {
  sql_driver = pgsql
  passdb_sql_query = SELECT u.password_hash AS password \
    FROM "user" u \
    JOIN mailbox m ON m.user_id = u.id \
    JOIN mail_domain d ON d.id = m.domain_id \
    WHERE m.local_part = '%{user | username}' \
      AND d.name = '%{user | domain}' \
      AND m.is_active = true AND d.is_active = true
}

userdb sql {
  sql_driver = pgsql
  userdb_sql_query = SELECT '/var/vmail/%{user | domain}/%{user | username}' AS home, \
    5000 AS uid, 5000 AS gid, \
    (m.quota_bytes || 'B') AS quota_storage_size \
    FROM mailbox m \
    JOIN mail_domain d ON d.id = m.domain_id \
    WHERE m.local_part = '%{user | username}' \
      AND d.name = '%{user | domain}' \
      AND m.is_active = true AND d.is_active = true
}
Права mail_reader в PostgreSQL:

text
GRANT CONNECT ON DATABASE myframework TO mail_reader;
GRANT USAGE ON SCHEMA public TO mail_reader;
GRANT SELECT ON mail_domain TO mail_reader;
GRANT SELECT ON mailbox TO mail_reader;
GRANT SELECT ON "user" TO mail_reader;
GRANT UPDATE (last_login) ON mailbox TO mail_reader;
Важно: default_password_scheme не используется — Dovecot читает схему из префикса {ARGON2ID} в хэше.

4.8. Dovecot quota (per-user, Dovecot 2.4)
/etc/dovecot/conf.d/90-quota.conf:

text
quota_storage_size = 1G

quota "User quota" {
}
userdb_sql_query возвращает quota_storage_size = <bytes>B — переопределяет глобальный дефолт.

10-mail.conf:

text
mail_plugins = quota
(глобально, без $mail_plugins).

20-lmtp.conf:

text
protocol lmtp {
  mail_plugins = quota sieve
}
10-master.conf:

text
service auth-worker {
  vsz_limit = 2G
}
5. РЕАЛИЗОВАНО
5.1. W3 — Прикрепление файлов к статьям/страницам
Детали: docs/tasks/W3.md.

Кратко:

Модель ShareAttach.

Cloud: POST /api/internal-share/<file_id>.

Framework: /admin/api/cloud-tree, /admin/api/cloud-folder/<id>, /admin/api/cloud-files, /admin/api/attach-to-article, /admin/api/check-attachments/<file_id>.

UI модалки — core/templates/partials/file_manager_modal.html + core/static/js/attached-files.js.

UI статьи — плитки, AJAX-навигация по папкам, лайтбокс.

Логика сохранения — _process_attached_files_in_html.

Публичные страницы — /s/<token> в framework.

Коммиты: db7da8d, 47dad68, 713ff89, c4844eb, c0da1d9, c96a373, f84d087, abeb191, 3ca7cc6.

5.2. W31 — Toast-уведомления
CSS: .app-toast-* в core/static/css/style.css.

JS: core/static/js/toast.js — window.showToast(message, type, duration).

Типы: success / danger / warning / info.

Позиция: правый верхний угол (в планах — перенести в правый нижний, см. раздел 10).

Автозакрытие: 4 сек (danger — 6 сек).

Подключено в core_base.html и base_admin.html (отдельно, потому что base_admin.html — самостоятельный HTML, не наследуется от core_base.html).

Коммит: 4d5f2b8.

5.3. W32 — Убраны DEBUG-логи
В framework/app.py удалены print('[DEBUG] ...') из context_processor.

Коммит: 1b658dc.

5.4. W34 — Делегирование облака
Что реализовано:

_collect_user_assets(user_id) — собирает активы пользователя (файлы, шары, статьи, страницы, ящики почты).

GET /admin/users/<id>/delete — модалка user_delete_modal.html.

POST /admin/users/<id>/delete — удаление (если нет активов).

POST /admin/users/<id>/reassign — перенос активов + удаление.

Логика: папка «Унаследовано от <username> <date>» у получателя; файлы плоско в cloud_data/<new_uid>/.

Почта (W2): при удалении пользователя — все его Mailbox архивируются в cloud_data/<admin_uid>/_mail_archive/. Архивы доступны админу в облаке.

Коммит: 92ad44c.

5.5. W36 — Вкладка «Прикреплено к статьям» в облаке
list_attached_shares(owner_id) в cloud/cloud_service.py.

Маршрут /attached в cloud/app.py.

Шаблон cloud/templates/attached.html.

Коммит: 9472ce9.

5.6. W37 — Плитки в облаке + прогресс-бар
cloud/templates/index.html: таблица → сетка .cloud-tiles.

Прогресс-бар загрузки: .upload-files-list, .file-item-bar в cloud/static/css/cloud.css.

Коммит: d8d8ef3.

5.7. W38+W39 — Trash + предупреждение о привязках
trash_item в cloud_service.py — не удаляет CloudShare.

get_share_by_token — проверка is_trashed.

Cloud: /api/check-attachments/<file_id>.

UI: trashSelected проверяет привязки, показывает confirm.

Коммит: 59ee6b0.

5.8. W2 — Почта (✅ завершено)
Что реализовано:

Инфраструктура:

Postfix 3.10.13, Dovecot 2.4.1-4, Rspamd 3.12.1.

Пользователь vmail (uid/gid 5000).

Maildir: /var/vmail/<domain>/<local_part>/.

Роль mail_reader в PostgreSQL.

Postfix:

virtual_mailbox_domains, virtual_mailbox_maps — SQL к mail_domain, mailbox.

virtual_transport = lmtp:unix:private/dovecot-lmtp.

SASL через Dovecot, milter на Rspamd.

Dovecot:

SQL-аутентификация (passdb — из "user", userdb — из mailbox).

Maildir в /var/vmail/%{domain}/%{username}.

Квоты per-user (Dovecot 2.4, через quota_storage_size в userdb).

LMTP, Sieve.

vsz_limit = 2G для auth-worker (Argon2 memory-hard).

Rspamd:

dkim_signing.conf, milter_headers.conf.

Единый пароль (Argon2id):

User.set_password / check_password — Argon2id + префикс {ARGON2ID}.

Миграция — все пароли в БД получили префикс.

Dovecot читает User.password_hash — один пароль для framework/cloud/mail.

Mail-сервис (mail/):

Flask-приложение на :5004 (Gunicorn), Nginx на :5003.

SSO через общую cookie (.site.ru / Domain=192.168.2.19).

Главная: карточка ящика, использование, IMAP-настройки.

Смена пароля почты (страница).

Внутренний API: hash-password (legacy), quota, reload, archive-mailbox.

Админка (framework):

/admin/mail/ — CRUD доменов.

/admin/mail/domains/<id>/mailboxes/ — список ящиков домена.

/admin/settings/ — блок «Почтовые домены».

/admin/quotas/ — таблица с квотами облака и почты.

/admin/quotas/user/<id> — детали + секция «Почтовые ящики».

/admin/users/ — колонка «Почта».

/admin/users/create — секция «Почта» в форме (создание ящика).

/admin/users/<id>/edit — синхронизация пароля/квоты/local_part.

/admin/users/<id>/delete — архивация почты в облако админа.

Инфраструктура deploy:

deploy/setup-mail.sh — установка почты.

deploy/nginx/mail.conf, deploy/systemd/mail.service, deploy/sudoers/mail-restart.

deploy/templates/postfix/, deploy/templates/dovecot/, deploy/templates/rspamd/.

Ограничения:

Dovecot 2.4 — нестабильный (см. раздел 10).

Per-user квоты — работают, но через нестандартный механизм (quota_storage_size в userdb).

Архивация Maildir при удалении пользователя — синхронная (может зависнуть на больших ящиках). См. W41.

Mailbox.password_hash — legacy-поле, не используется (см. W45).

Коммиты: 3267db8, 073c19b.

6. В РАБОТЕ
(пусто)

7. ЗАПЛАНИРОВАНО
7.1. W25 — Рефакторинг альбомов
Цель: «Альбом = папка облака».

Статус: ТЗ готово (отдельно), не начато.

Приоритет: средний.

Оценка: большая задача.

7.2. W33 — Утилита сканирования ShareAttach
Раздел /admin/attachments/.

Список файлов с привязками.

Действия: отвязать, перейти, скачать.

Обратный отчёт: файлы-сироты.

Приоритет: средний. Оценка: 1–2 часа.

7.3. W35 — Закрытая шара
UI создания шары: пароль, срок, лимит скачиваний.

/s/<token> — форма ввода пароля.

Проверка пароля, сессия доступа.

Сообщения «Ссылка истекла» / «Лимит скачиваний».

Приоритет: средний. Оценка: 1–2 часа.

7.4. W40 — Подготовка к боевому
Что входит:

HTTPS: Certbot + Let's Encrypt (SAN на site.ru, cloud.site.ru, mail.site.ru).

Поддомены вместо портов.

SESSION_COOKIE_SECURE = True, SESSION_COOKIE_DOMAIN = '.site.ru'.

PERMANENT_SESSION_LIFETIME = timedelta(days=30), SESSION_COOKIE_MAX_AGE.

ProxyFix (x_proto, x_host).

Nginx: listen 443 ssl http2, редирект с 80.

HSTS.

Смена всех паролей (deploy, PostgreSQL, admin).

Уведомление в админке о сроке SSL.

Тест SSL Labs (цель A).

Приоритет: высокий. Оценка: 1 день.

7.5. W41 — Асинхронные операции с прогрессбаром
Проблема: удаление пользователя (архивация почты + reassign облака) — синхронное. На больших объёмах зависает HTTP-запрос.

Что делать:

Модель Task в БД.

Фоновый воркер (thread / Celery / RQ).

Страница задачи с прогрессбаром (/admin/tasks/<id>).

Polling через /api/tasks/<id>.

Откат при ошибке.

Приоритет: средний. Оценка: 2–3 дня.

7.6. W42 — Утилита чистки мусора
Страница /admin/maintenance/.

Что чистит:

Мёртвые Maildir'ы — директории /var/vmail/<domain>/<local_part>/, для которых нет записи в mailbox.

Мёртвые шары (CloudShare) — без ShareAttach.

Мёртвые FileUsage — ссылки на несуществующие сущности.

Мёртвые CloudFile — записи без файлов на диске.

Осиротевшие файлы на диске — файлы в cloud_data/<uid>/ без записи в БД.

Старые архивы в /tmp — .tar.gz от неудачных операций.

Периодическая проверка: cron / systemd timer + уведомление админа.

Приоритет: низкий. Оценка: 1–2 дня.

7.7. W43 — Рассмотреть альтернативу Dovecot
Причины: Dovecot 2.4 сломал совместимость, документация противоречива, сообщество недовольно.

Кандидаты:

Stalwart (Rust, всё в одном).

Cyrus IMAP (зрелый).

Приоритет: низкий (пока работает 2.4). Оценка: большая задача.

7.8. W44 — Мониторинг обновлений Dovecot 2.4
Что делать:

Следить за стабильностью 2.4.x.

При появлении стабильной версии (2.4.5+ или 2.5) — обновить шаблоны и setup-mail.sh.

apt-mark hold — уже зафиксированы версии.

Приоритет: низкий.

7.9. W45 — Удалить Mailbox.password_hash
Причина: legacy-поле, не используется (пароль — в User.password_hash).

Что делать:

Миграция: ALTER TABLE mailbox DROP COLUMN password_hash.

Обновить модели, SQL-запросы.

Убедиться, что нигде не используется.

Приоритет: низкий. Оценка: 1 час.

7.10. W15 — Бэкап почты
Что делать:

Бэкап /var/vmail/ в /mnt/backup/.

Cron / systemd timer.

Ротация архивов.

Приоритет: средний (после W40).

### 7.11. W47 — UI почты (полный, Gmail-like)

**Цель:** полноценный веб-интерфейс для работы с почтой.

**Что входит:**
- Чтение, отправка, ответы, пересылка.
- Папки (стандартные + свои).
- Sieve-правила.
- Поиск (IMAP SEARCH).
- Вложения (local + облако).
- Черновики (автосохранение).
- Уведомления (toast, счётчики).
- Настройки (минимум).
- Безопасность (bleach, CSP, master-user).

**Детали:** `docs/tasks/W47.md`.

**Оценка:** 6–8 недель.

**Приоритет:** высокий.

---

### 7.12. W48 — Совместное редактирование файлов (Яндекс.360-like)

**Цель:** одновременное редактирование одного файла несколькими пользователями.

**Детали:** `docs/tasks/W48.md`.

**Оценка:** 1–2 месяца.

**Приоритет:** средний.

---

### 7.13. W49 — Мобильный UI почты

**Цель:** отдельный mobile-first UI (одна панель за раз).

**Детали:** `docs/tasks/W49.md`.

**Оценка:** 2–3 недели.

**Приоритет:** средний.

---

### 7.14. W50 — Адресная книга

**Цель:** полная адресная книга — контакты, группы, импорт/экспорт.

**Детали:** `docs/tasks/W50.md`.

**Оценка:** 1–2 недели.

**Приоритет:** средний.

---

### 7.15. W51 — Полнотекстовый поиск (FTS)

**Цель:** быстрый полнотекстовый поиск через Dovecot FTS.

**Детали:** `docs/tasks/W51.md`.

**Оценка:** 2–3 недели.

**Приоритет:** средний.

---

### 7.16. W52 — Метки (labels / keywords)

**Цель:** гибкая категоризация писем через IMAP keywords.

**Детали:** `docs/tasks/W52.md`.

**Оценка:** 1–2 недели.

**Приоритет:** низкий.

---

### 7.17. W53 — Расширенные Sieve-правила

**Цель:** логические операторы, regex, каскадные действия.

**Детали:** `docs/tasks/W53.md`.

**Оценка:** 1–2 недели.

**Приоритет:** средний.

---

### 7.18. W54 — Расширенные настройки почты

**Цель:** автоответ, пересылка, темы, уведомления, хранение.

**Детали:** `docs/tasks/W54.md`.

**Оценка:** 1–2 недели.

**Приоритет:** средний.

---

### 7.19. W55 — Расширенные логи и аудит

**Цель:** расширенное логгирование + UI в админке.

**Детали:** `docs/tasks/W55.md`.

**Оценка:** 3–5 дней.

**Приоритет:** низкий.

---

### 7.20. W56 — UI ошибок в админке

**Цель:** `/admin/errors/` — просмотр ErrorLog.

**Детали:** `docs/tasks/W56.md`.

**Оценка:** 3–5 дней.

**Приоритет:** низкий.

---

### 7.21. W57 — Browser notifications и звук

**Цель:** расширенные уведомления (Notification API, звук).

**Детали:** `docs/tasks/W57.md`.

**Оценка:** 3–5 дней.

**Приоритет:** низкий.

8. ИДЕИ (низкий приоритет)
X1. Блочный редактор вместо TinyMCE
Заменить TinyMCE на блочный редактор (Notion-like). Кандидаты: Yiitap, Tiptap, Blok, Gutenberg.

Следствие: смена архитектуры хранения контента (HTML → JSON блоков).

Приоритет: идея.

X2. Криптопровайдер (ЭЦП)
Интеграция КриптоПро для подписи документов.

Приоритет: идея.

9. ИЗВЕСТНЫЕ БАГИ
БАГ-W2-001 — вёрстка user_delete_modal.html
Проблема: строки накладываются/ломаются.

Приоритет: низкий (косметика).

БАГ-W2-005 — карточки на странице деталей пользователя
Проблема: на /admin/quotas/user/<id> верхние карточки (роль, занято, квота, использование) — только про облако. Информация о почте — ниже, в отдельной секции.

Что сделать: сгруппировать (отдельная карточка/секция про почту) или вкладки «Облако»/«Почта».

Приоритет: низкий (косметика).

БАГ-W2-006 — кэш браузера на /admin/quotas/
Проблема: после изменения квоты почты на /admin/quotas/user/<id>, возврат на /admin/quotas/ не показывает новое значение (browser cache).

Что сделать: no-cache для страницы или AJAX-обновление.

Приоритет: низкий.

Удаление файла в облаке не проверяет привязки
Проблема: удаление по иконке в строке облака не проверяет ShareAttach (в отличие от массового trashSelected).

Приоритет: средний.

favicon.ico — 404
На некоторых страницах — 404. Приоритет: низкий.

10. КОСМЕТИКА
Перенос toast в правый нижний угол
Проблема: toast перекрывает шапку админки.

Что сделать: перенести .app-toast-container в правый нижний угол.

Файлы: core/static/js/toast.js, core/static/css/style.css.

Приоритет: низкий.

11. ПРАВИЛА РАБОТЫ
Общие
Одно действие — один шаг. Ждать результата.

Не коммитить без проверки (git status / git diff).

Не трогать прод без нужды.

Бэкап БД перед критичными правками.

Комментарии в коде — на русском.

Стиль — рабочий, по делу, с аргументацией.

Технические
sed -n 'N,Mp' — только с числами.

Перед патчем — присылать диагностику (sed, grep, journalctl).

Для больших файлов — VS Code, не heredoc.

GitHub-ссылки — только на файлы (tree/ не работает).

После правок шаблонов/Python — sudo systemctl restart framework (или cloud/mail).

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

Пароли: argon2-cffi, префикс {ARGON2ID}, Dovecot читает из "user".

Mailbox.password_hash — не использовать (legacy).

12. ПОЛЕЗНЫЕ КОМАНДЫ
bash
# Перезапуск сервисов
sudo systemctl restart framework cloud mail
sudo systemctl status framework cloud mail --no-pager
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
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5004/

# SQL
sudo -u postgres psql myframework
echo 'SELECT * FROM share_attach;' | sudo -u postgres psql myframework

# Почта
sudo doveadm auth test test@testprod2.local admin123
sudo doveadm user test@testprod2.local
sudo doveadm quota get -u test@testprod2.local
sudo doveadm pw -s SHA512-CRYPT -p 'password'

# Права mail_reader
GRANT SELECT ON "user" TO mail_reader;
GRANT SELECT ON mailbox TO mail_reader;
GRANT SELECT ON mail_domain TO mail_reader;
13. ИСТОРИЯ КОММИТОВ
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
—	Стилизация attached + цвета иконок	3ca7cc6
W34	Делегирование активов при удалении пользователя	92ad44c
W2	Модели почты, User.mail_quota_bytes, шаблоны, setup-mail.sh	388b195
W2	Единый пароль (Argon2id), Dovecot SQL, mail-сервис, квоты	3267db8
W2	Админка — /admin/quotas/, домены, почта в пользователях	073c19b
14. СЛЕДУЮЩИЙ ШАГ
Рекомендации:

W40 — подготовка к боевому (HTTPS, сессии, поддомены).

W41 — асинхронные операции с прогрессбаром (для удаления пользователя).

W33 — утилита ShareAttach.

W35 — закрытая шара.

W42 — чистка мусора.

W25 — рефакторинг альбомов.

Рекомендация: W40 → W41 → W33 → W35 → W42 → W25.

15. КАК ОБНОВЛЯТЬ ЭТОТ ФАЙЛ
После каждой задачи:

Перенести из «Запланировано» в «Реализовано».

Обновить: что сделано, где, коммиты, ограничения.

Добавить коммит в «История».

Обновить «Следующий шаг».

Новые задачи: добавить в «Запланировано» (с приоритетом, оценкой).

Баги: добавить в «Известные баги».

Идеи: добавить в «Идеи».

При старте нового чата: сообщить ссылку на SPEC.md + задачу.
