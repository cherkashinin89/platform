# Реестр эндпоинтов

Сгенерировано: 2026-10-29 12:34, коммит `3090ad7`.

**НЕ ПРАВИТЬ РУКАМИ** — генерируется deploy/gen_routes.py.

## framework

| Метод | Путь | Endpoint | Категория | Назначение | Файл:функция |
|---|---|---|---|---|---|
| GET | `/` | index | public | Главная страница сайта с пагинацией статей | `app.py:index` |
| GET | `/admin/` | admin_dashboard | admin | Главная страница админ-панели | `app.py:admin_dashboard` |
| GET | `/admin/albums/` | admin_albums | admin | Список альбомов в админке | `app.py:admin_albums` |
| POST | `/admin/albums/<int:album_id>/cover/<int:photo_id>` | admin_album_set_cover | admin | W3: звезда — сделать фото обложкой И отправить в слайдер. | `app.py:admin_album_set_cover` |
| POST | `/admin/albums/<int:album_id>/photos/<int:photo_id>/delete` | admin_album_photo_delete | admin | Удаление фото из альбома (облачный файл остаётся в облаке) | `app.py:admin_album_photo_delete` |
| POST | `/admin/albums/<int:album_id>/reorder` | admin_album_reorder | admin | Сохранение нового порядка фото (перетаскивание, JSON) | `app.py:admin_album_reorder` |
| POST | `/admin/albums/<int:id>/delete` | admin_album_delete | admin | Удаление альбома (облачные файлы остаются в облаке) | `app.py:admin_album_delete` |
| GET, POST | `/admin/albums/<int:id>/edit` | admin_album_edit | admin | Редактирование альбома + управление фотографиями | `app.py:admin_album_edit` |
| GET, POST | `/admin/albums/create` | admin_album_create | admin | Создание альбома | `app.py:admin_album_create` |
| POST | `/admin/albums/reorder` | admin_albums_reorder | admin | Сохранение нового порядка альбомов (JSON) | `app.py:admin_albums_reorder` |
| GET | `/admin/api/check-attachments/<int:file_id>` | admin_api_check_attachments | admin | Проверяет, к каким статьям и страницам привязан файл. | `app.py:admin_api_check_attachments` |
| GET | `/admin/api/cloud-files` | admin_api_cloud_files | admin | JSON-список облачных файлов для модального окна редактора. | `app.py:admin_api_cloud_files` |
| GET | `/admin/api/cloud-folder/<int:folder_id>` | admin_api_cloud_folder | admin | JSON-содержимое папки облака (для модалки выбора файлов). | `app.py:admin_api_cloud_folder` |
| GET | `/admin/api/cloud-tree` | admin_api_cloud_tree | admin | JSON-дерево папок текущего пользователя (для модалки выбора файлов). | `app.py:admin_api_cloud_tree` |
| GET | `/admin/api/disk-status` | admin_api_disk_status | admin | JSON со статусом внешнего диска — для обновления в реальном времени | `app.py:admin_api_disk_status` |
| GET | `/admin/api/files` | admin_api_files | admin | JSON-список файлов для модального окна редактора | `app.py:admin_api_files` |
| GET | `/admin/api/service-status` | admin_api_service_status | admin | Возвращает статус сервиса myframework | `app.py:admin_api_service_status` |
| GET | `/admin/api/system-stats` | admin_api_system_stats | admin | JSON с текущими метриками сервера | `app.py:admin_api_system_stats` |
| POST | `/admin/api/upload` | admin_api_upload | admin | AJAX-загрузка файла из редактора | `app.py:admin_api_upload` |
| POST | `/admin/api/upload-multiple` | admin_api_upload_multiple | admin | AJAX-загрузка нескольких файлов (из редактора) | `app.py:admin_api_upload_multiple` |
| GET | `/admin/articles/` | admin_articles | admin | Список статей с пагинацией и поиском | `app.py:admin_articles` |
| POST | `/admin/articles/<int:id>/delete` | admin_article_delete | admin | Удаление статьи | `app.py:admin_article_delete` |
| GET, POST | `/admin/articles/<int:id>/edit` | admin_article_edit | admin | Редактирование существующей статьи | `app.py:admin_article_edit` |
| GET, POST | `/admin/articles/create` | admin_article_create | admin |  | `app.py:admin_article_create` |
| GET | `/admin/files/` | admin_files | admin | Список файлов с пагинацией, сортировкой, фильтром и поиском (Python-фильтрация) | `app.py:admin_files` |
| POST | `/admin/files/<int:id>/delete` | admin_file_delete | admin | Удаление файла | `app.py:admin_file_delete` |
| GET | `/admin/files/<int:id>/download` | admin_file_download | admin | Скачивание файла | `app.py:admin_file_download` |
| GET, POST | `/admin/files/archive` | admin_files_archive | admin | Архивация файлов за указанный период | `app.py:admin_files_archive` |
| POST | `/admin/files/upload` | admin_file_upload | admin | Массовая загрузка файлов из формы | `app.py:admin_file_upload` |
| GET | `/admin/mail/` | admin_mail_domains | admin | Список почтовых доменов. | `app.py:admin_mail_domains` |
| POST | `/admin/mail/domains/<int:domain_id>/delete` | admin_mail_domain_delete | admin | Удаление почтового домена. | `app.py:admin_mail_domain_delete` |
| GET, POST | `/admin/mail/domains/<int:domain_id>/edit` | admin_mail_domain_edit | admin | Редактирование почтового домена. | `app.py:admin_mail_domain_edit` |
| GET | `/admin/mail/domains/<int:domain_id>/mailboxes/` | admin_mail_mailboxes | admin | Список ящиков в домене. | `app.py:admin_mail_mailboxes` |
| GET, POST | `/admin/mail/domains/<int:domain_id>/mailboxes/new` | admin_mail_mailbox_new | admin | Создание ящика в домене. | `app.py:admin_mail_mailbox_new` |
| GET, POST | `/admin/mail/domains/new` | admin_mail_domain_new | admin | Создание почтового домена. | `app.py:admin_mail_domain_new` |
| POST | `/admin/mail/mailboxes/<int:mailbox_id>/delete` | admin_mail_mailbox_delete | admin | Удаление ящика. | `app.py:admin_mail_mailbox_delete` |
| GET, POST | `/admin/mail/mailboxes/<int:mailbox_id>/edit` | admin_mail_mailbox_edit | admin | Редактирование ящика. | `app.py:admin_mail_mailbox_edit` |
| GET | `/admin/menu/` | admin_menu | admin | Список пунктов меню | `app.py:admin_menu` |
| POST | `/admin/menu/<int:id>/delete` | admin_menu_delete | admin | Удаление пункта меню | `app.py:admin_menu_delete` |
| GET, POST | `/admin/menu/<int:id>/edit` | admin_menu_edit | admin | Редактирование пункта меню | `app.py:admin_menu_edit` |
| GET, POST | `/admin/menu/create` | admin_menu_create | admin | Создание пункта меню | `app.py:admin_menu_create` |
| GET | `/admin/pages/` | admin_pages | admin | Список страниц с поиском | `app.py:admin_pages` |
| POST | `/admin/pages/<int:id>/delete` | admin_page_delete | admin | Удаление страницы | `app.py:admin_page_delete` |
| GET, POST | `/admin/pages/<int:id>/edit` | admin_page_edit | admin | Редактирование существующей страницы | `app.py:admin_page_edit` |
| GET, POST | `/admin/pages/create` | admin_page_create | admin | Создание новой страницы | `app.py:admin_page_create` |
| GET | `/admin/quotas/` | admin_quotas | admin | Список всех пользователей с квотами облака и почты. | `app.py:admin_quotas` |
| GET | `/admin/quotas/user/<int:user_id>` | admin_quota_user_detail | admin | Детали пользователя: файлы, квоты облака и почты, действия. | `app.py:admin_quota_user_detail` |
| GET | `/admin/quotas/user/<int:user_id>/download/<int:file_id>` | admin_quota_user_download | admin | Скачивание файла пользователя (только admin). | `app.py:admin_quota_user_download` |
| POST | `/admin/quotas/user/<int:user_id>/mail-quota/<int:mailbox_id>` | admin_quota_user_mail_quota | admin | Обновление квоты почтового ящика. | `app.py:admin_quota_user_mail_quota` |
| GET | `/admin/quotas/user/<int:user_id>/quota` | admin_quota_user_quota | admin | Изменение квоты пользователя. | `app.py:admin_quota_user_quota` |
| GET | `/admin/quotas/user/<int:user_id>/trash` | admin_quota_user_trash | admin | Полная очистка корзины пользователя. | `app.py:admin_quota_user_trash` |
| GET, POST | `/admin/settings/` | admin_settings | admin | Страница настроек сайта: резервное копирование + общие настройки | `app.py:admin_settings` |
| POST | `/admin/settings/backup` | admin_settings_backup | admin | Запуск полного бэкапа на внешний диск | `app.py:admin_settings_backup` |
| POST | `/admin/settings/mount` | admin_settings_mount | admin | Монтирование внешнего диска | `app.py:admin_settings_mount` |
| POST | `/admin/settings/restart` | admin_settings_restart | admin | Перезапуск сервиса myframework через systemd | `app.py:admin_settings_restart` |
| POST | `/admin/settings/sync` | admin_settings_sync | admin | Принудительная синхронизация буферов диска | `app.py:admin_settings_sync` |
| POST | `/admin/settings/unmount` | admin_settings_unmount | admin | Безопасное отмонтирование внешнего диска | `app.py:admin_settings_unmount` |
| GET | `/admin/users/` | admin_users | admin | Список пользователей с пагинацией | `app.py:admin_users` |
| GET, POST | `/admin/users/<int:id>/delete` | admin_user_delete | admin | W34: удаление пользователя. | `app.py:admin_user_delete` |
| GET, POST | `/admin/users/<int:id>/edit` | admin_user_edit | admin | Редактирование пользователя + синхронизация почтового ящика | `app.py:admin_user_edit` |
| POST | `/admin/users/<int:id>/reassign` | admin_user_reassign | admin | W34: передача активов пользователя другому + удаление. | `app.py:admin_user_reassign` |
| GET, POST | `/admin/users/create` | admin_user_create | admin | Создание нового пользователя (+ опционально почтового ящика) | `app.py:admin_user_create` |
| GET | `/article/<int:id>` | show_article | public | Отображение статьи по ID | `app.py:show_article` |
| GET | `/articles` | articles_list | public | Публичный список всех опубликованных статей с пагинацией | `app.py:articles_list` |
| GET | `/files/<int:file_id>` | serve_cloud_file | public | W58: безопасная отдача файла из облака (X-Accel-Redirect). | `app.py:serve_cloud_file` |
| GET | `/gallery` | gallery_index | public | Список опубликованных альбомов | `app.py:gallery_index` |
| GET | `/gallery/<slug>` | gallery_album | public | Страница альбома с миниатюрами и каруселью | `app.py:gallery_album` |
| GET, POST | `/login` | login | public | Страница входа в систему + приём формы из шапки | `app.py:login` |
| GET | `/logout` | logout | auth | Выход из системы | `app.py:logout` |
| GET | `/media/<int:file_id>` | serve_media | public |  | `app.py:serve_media` |
| GET | `/page/<slug>` | show_page | public | Отображение статической страницы по slug | `app.py:show_page` |
| GET | `/s/<token>` | public_share_view | public | W3: публичная страница шары (файл или папка) в контексте framework. | `app.py:public_share_view` |
| POST | `/s/<token>/auth` | public_share_auth | public | W35: приём пароля шары. При успехе — отметка в сессии и редирект. | `app.py:public_share_auth` |
| GET | `/s/<token>/download` | public_share_download | public | W3: скачивание файла, на который создана шара (framework). W35: +лимит. | `app.py:public_share_download` |
| GET | `/s/<token>/download/<int:file_id>` | public_share_download_file | public | W3: скачивание файла из папки-шары (framework). | `app.py:public_share_download_file` |
| GET | `/search` | search | public | Публичный поиск по статьям, страницам и файлам | `app.py:search` |
| GET | `/uploads/<path:filename>` | uploaded_file | public | Публичная отдача файлов из uploads/ | `app.py:uploaded_file` |
| GET | `/view/<int:file_id>` | view_cloud_file | public | W59: JSON для просмотра офисного файла (read-only, Collabora). | `app.py:view_cloud_file` |

## cloud

| Метод | Путь | Endpoint | Категория | Назначение | Файл:функция |
|---|---|---|---|---|---|
| GET | `/` | index | auth | Главная страница облака: список файлов в корне или в папке. | `app.py:index` |
| GET | `/api/check-attachments/<int:file_id>` | api_check_attachments | auth | W39: проверяет, привязан ли файл к статьям/страницам. | `app.py:api_check_attachments` |
| GET | `/api/collabora-status` | wopi.collabora_status | public | Проверка доступности Collabora (для JS). | `wopi.py:collabora_status` |
| POST | `/api/delete-permanent/<int:item_id>` | api_delete_permanent | auth | Полное удаление: файл с диска + запись из БД. | `app.py:api_delete_permanent` |
| GET | `/api/download/<int:file_id>` | api_download | auth | Отдаёт файл пользователю. | `app.py:api_download` |
| POST | `/api/folder` | api_create_folder | auth | Создаёт папку. | `app.py:api_create_folder` |
| POST | `/api/internal-share/<int:file_id>` | api_internal_share | internal | Создаёт/переиспользует шару на файл от имени пользователя. | `app.py:api_internal_share` |
| POST | `/api/move` | api_move | auth | Перемещает элемент(ы) в новую папку. | `app.py:api_move` |
| POST | `/api/rename/<int:item_id>` | api_rename | auth | Переименовывает файл или папку. | `app.py:api_rename` |
| POST | `/api/restore/<int:item_id>` | api_restore | auth | Восстанавливает элемент из корзины. | `app.py:api_restore` |
| POST | `/api/share/<int:item_id>` | api_share | auth | W35: создаёт ссылку с ограничениями (пароль, срок, лимит, is_public). | `app.py:api_share` |
| POST | `/api/share/revoke/<int:share_id>` | api_share_revoke | auth | Отзывает публичную ссылку. | `app.py:api_share_revoke` |
| POST | `/api/trash/<int:item_id>` | api_trash | auth | Мягкое удаление: помещает элемент и всех потомков в корзину. | `app.py:api_trash` |
| GET | `/api/tree` | api_tree | auth | Возвращает плоский список всех папок пользователя (не в корзине). | `app.py:api_tree` |
| POST | `/api/upload` | api_upload | auth | Загружает один или несколько файлов. | `app.py:api_upload` |
| GET | `/api/versions/<int:file_id>` | wopi.list_versions | auth | Список версий файла (история). | `wopi.py:list_versions` |
| POST | `/api/versions/<int:file_id>/restore/<int:version_id>` | wopi.restore_version | auth | Откат к указанной версии (с сохранением текущей как новой версии). | `wopi.py:restore_version` |
| POST | `/api/wopi-token/<int:file_id>` | wopi.create_wopi_token | wopi | Создаёт WOPI-токен для файла (владелец или получатель шары с can_edit). | `wopi.py:create_wopi_token` |
| GET | `/attached` | attached | auth | W36: страница «Прикреплено к статьям» — список привязанных файлов. | `app.py:attached` |
| GET | `/collabora` | collabora | public |  | `app.py:collabora` |
| GET | `/folder/<int:folder_id>` | index | auth | Главная страница облака: список файлов в корне или в папке. | `app.py:index` |
| GET | `/s/<token>` | public_share | public | Публичная страница по ссылке-шарингу. | `app.py:public_share` |
| GET | `/s/<token>/download` | public_share_download | public | Скачивание файла, на который создан шаринг. | `app.py:public_share_download` |
| GET | `/s/<token>/download/<int:file_id>` | public_share_download_file | public | Скачивание конкретного файла из папки, доступной по шарингу. | `app.py:public_share_download_file` |
| GET | `/shares` | shares | auth | Страница со списком всех публичных ссылок пользователя. | `app.py:shares` |
| GET | `/trash` | trash | auth | Страница корзины: список удалённых элементов. | `app.py:trash` |
| GET | `/whoami` | whoami | auth | Показывает данные текущего пользователя — для отладки. | `app.py:whoami` |
| GET | `/wopi/files/<int:file_id>` | wopi.wopi_check_file_info | wopi | CheckFileInfo — метаданные файла + права. | `wopi.py:wopi_check_file_info` |
| GET | `/wopi/files/<int:file_id>/contents` | wopi.wopi_get_file | wopi | GetFile — отдаём содержимое файла. | `wopi.py:wopi_get_file` |
| POST | `/wopi/files/<int:file_id>/contents` | wopi.wopi_put_file | wopi | PutFile — сохраняем изменения в файл. | `wopi.py:wopi_put_file` |
