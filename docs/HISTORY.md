# История изменений platform

Актуально на: 2026-10-29.

Правила:
- Новые записи — сверху.
- Одна задача = одна запись (внутри — список коммитов).
- Детали (эндпоинты, файлы, нюансы) — в `tasks/Wxx.md`; здесь кратко + ссылка.
- Вехи без W-номера — `M1`, `M2`, … (инфраструктура, реорганизации).

Формат записи:

```
### Wxx — Название (дата, коммит `abc1234`)
Что: 1–2 строки.
Ключевое: модель/эндпоинты/UI (1–3 пункта).
Детали: docs/tasks/Wxx.md
```

---

## Вехи

### M1 — Монорепо создано (окт. 2026)
Что: объединение `myframework` и `mycloud` в единый репозиторий `platform`.
Ключевое: общий пакет `core` (модели, расширения, утилиты); два Flask-приложения — `framework` (сайт+админка) и `cloud` (облако); сервисы `mail` (почта) и `collabora` (Docker).
Коммиты: 6fc0d74 (skeleton), 4dbaeb8/55c52c3 (перенос framework/cloud), 909bb78 (пакет core), deb014d (единый deploy/).

### M2 — Единая история миграций (2026-10, коммит 0d5cca0)
Что: миграции, которые раньше велись отдельно в framework/cloud/mail, сведены в core/migrations.
Ключевое: Flask-Migrate в framework с directory=core/migrations; единый head для всех сервисов.

---

## Задачи

### W35 — Закрытая шара: is_public, пароль, срок, лимит (2026-10-29, коммит 296af5a)
Что: ограничения для CloudShare — пароль (Argon2id), срок действия, лимит скачиваний, режим public/только-логин.
Ключевое: CloudShare.is_public + миграция 616fd1a65e3f; POST /api/share/<id> принимает JSON-параметры; /s/<token> — gate (is_public/пароль), /s/<token>/auth, инкремент download_count; UI — двухфазная модалка.
Детали: docs/tasks/W35.md

### W59 — Просмотр офисных файлов read-only (2026-10-28, коммит 49a7c52)
Что: просмотр docx/xlsx/pptx без редактирования через Collabora.
Ключевое: SiteSettings.collabora_base_url (без хардкода); /view/<id> (JSON read-only); модалка file-viewer.js; /collabora переименован из /test_collabora; wopi_test.py → wopi.py.
Детали: docs/tasks/W59.md

### W58 — X-Accel-Redirect: ContentFile вместо ShareAttach (2026-10-28, коммиты bc71da8, 49a7c52)
Что: убраны костыли прикрепления файлов; файлы отдаются через /files/<id> (Nginx internal).
Ключевое: модель ContentFile (замена ShareAttach) + миграция; /files/<id> (X-Accel-Redirect); nginx /protected_files/ (internal); api_check_attachments на ContentFile.
Детали: docs/tasks/W58.md

### W48 — Collabora v1: редактирование офисных файлов (2026-10-27..28, коммиты d517666..7a23cec)
Что: редактирование docx/xlsx/pptx онлайн, права can_edit, история версий.
Ключевое: WopiToken (CheckFileInfo/GetFile/PutFile), CloudFileVersion (история), /collabora (редактор), /api/wopi-token/<id>, can_edit в CloudShare; обработка недоступности Collabora.
Детали: docs/tasks/W48.md
### W47 — UI почты, полный (Gmail-like) (2026-10-26..28, серия коммитов 73bb77e..d86dc94)
Что: полноценный веб-интерфейс почты поверх Dovecot/IMAP.
Ключевое: IMAP-клиент (imap_client.py), inbox/folder/message, кэш тел писем (Flask-Caching); compose (TinyMCE), автосохранение черновиков, reply/reply-all/forward; вложения (в т.ч. из облака); Sieve-правила (CRUD, активация); счётчик непрочитанных; master-user Dovecot; bleach-санитайз.
Статус: этапы 1–8 выполнены. Этап 9 (полировка) → POLISH.md; тесты — отдельно. Расширения вынесены: W49 (мобильный UI), W51 (FTS-поиск), W53 (Sieve+), W54 (настройки+), W55 (логи/аудит), W57 (notifications).
Детали: docs/tasks/W47.md

### W38/W39 — Trash и шары: предупреждения о привязках (2026-10, коммит 59ee6b0)
Что: файл в корзине не удаляет шары; предупреждение о привязках к контенту; фикс двойных имён в shares.
Ключевое: get_share_by_token отсекает файл в корзине; проверка FileUsage/ContentFile перед удалением.

### W37 — Плитки в облаке + прогресс-бар загрузки (2026-10, коммит d8d8ef3)
Что: вид плиткой в облаке, индикация прогресса загрузки файлов.

### W36 — Вкладка «Прикреплено к статьям» в облаке (2026-10, коммит 9472ce9)
Что: вкладка со списком файлов, привязанных к статьям/страницам.

### W34 — Делегирование активов при удалении пользователя (2026-10, коммит 92ad44c)
Что: при удалении пользователя его активы (файлы/контент) передаются другому пользователю.

### W32 — Убраны print-отладки из menu (2026-10, коммит 1b658dc)
Что: чистка отладочного вывода.

### W31 — Toast-уведомления (2026-10, коммит 4d5f2b8)
Что: стек toast-уведомлений в правом верхнем углу.
### W3 — Прикрепление файлов к статьям/страницам (2026-10, коммиты db7da8d..f84d087)
Что: механизм вставки файлов облака в статьи/страницы (ShareAttach).
Ключевое: модель ShareAttach + миграция; внутренний API cloud (internal-share) с X-Internal-Key; framework API cloud-tree/cloud-folder/check-attachments; модалка + AJAX-навигация; логика сохранения при create/edit/delete.
Статус: реализовано, **заменено W58** (ContentFile, /files/<id>).
Детали: docs/tasks/W3.md


