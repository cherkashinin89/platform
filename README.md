# platform

Монорепозиторий экосистемы:
- **core** — общий пакет (модели, auth, утилиты, шаблоны, CSS, миграции).
- **framework** — сайт + админка (контент, галерея, файлы, почта в админке).
- **cloud** — облачное хранилище (файлы, шары, квоты, Collabora).
- **mail** — почта (Flask-сервис: IMAP, SMTP, Sieve, настройки).
- **collabora** — Collabora Online (Docker, WOPI).
- **deploy** — общие конфиги развёртывания (Nginx, systemd, sudoers, шаблоны Postfix/Dovecot/Rspamd).

## Стек

- Python 3.13.5, Flask 3, PostgreSQL 17, Argon2id (единый пароль).
- Postfix + Dovecot 2.4 + Rspamd (почта).
- Collabora Online (CODE) 26.04, Docker (редактирование/просмотр офисных файлов).
- Bootstrap 5, TinyMCE 7 (локально, без CDN).

## Разработка

Каждый сервис имеет **собственный venv** и `requirements.txt`.
**Общий `.env`** в корне — единый `SECRET_KEY` для SSO.

Установка `core` в venv каждого проекта:
```bash
cd framework   # или cloud, mail
source venv/bin/activate
pip install -e ../core
Миграции
Единый источник правды — core/migrations/ (Alembic).
framework/cloud/mail не имеют своих migrations/.

bash
cd framework && source venv/bin/activate
flask db migrate -m "описание"
flask db upgrade
(путь к core/migrations/ задан в Migrate.init_app(directory=...)).

Развёртывание
См. deploy/README.md и deploy/setup.sh.

Порядок:

deploy/setup.sh — framework + cloud (venv, systemd, Nginx, sudoers).

deploy/setup-mail.sh — почта (Postfix, Dovecot, Rspamd, mail_reader, master-user).

collabora/docker-compose.yml — Collabora (Docker).

Nginx: deploy/nginx/{framework,cloud,mail,collabora}.conf.

flask create-admin — создание администратора (интерактивно).

Nginx (W58): location /protected_files/ { internal; alias .../cloud_data/; } — для X-Accel-Redirect.

Почта (W2)
Postfix 3.10, Dovecot 2.4, Rspamd 3.12.

mail_reader (PostgreSQL): GRANT SELECT на user, mailbox, mail_domain.

MAIL_* в .env.

master-user Dovecot: /etc/dovecot/master-users (chown root:dovecot, chmod 0640).

Collabora (W48/W59)
collabora/docker-compose.yml (образ collabora/code).

Nginx :5005 → 127.0.0.1:9980 (WebSocket).

WOPI: cloud/wopi.py (CheckFileInfo, GetFile, PutFile).

Редактирование: /collabora (облако). Просмотр: /view/<id> (framework, read-only).

URL — из SiteSettings.collabora_base_url.

Тестовые реквизиты
См. docs/SPEC.md (раздел 1.3). Сменить при боевом.

История
Монорепо создано в октябре 2026 объединением myframework и mycloud.
W2 (почта), W48 (Collabora), W58 (X-Accel-Redirect), W59 (просмотр) — завершены.