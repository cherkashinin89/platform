# core/__init__.py
# Общий пакет экосистемы platform.
#
# Содержит:
#   - models       — SQLAlchemy-модели (User, Article, CloudFile, ...)
#   - extensions   — db, login_manager, csrf, migrate
#   - auth         — декораторы ролей (admin_required, editor_required, ...)
#   - config       — CoreConfig (базовая конфигурация)
#   - utils        — общие утилиты (файлы, slug, статистика, бэкапы)

__version__ = '0.1.0'
