import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# Alembic Config object
config = context.config

# Logging
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # Flask-SQLAlchemy < 3
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy >= 3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Offline-режим миграций (SQL-скрипт без подключения)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        version_table='alembic_version_cloud',   # ← отдельная таблица версий
    )

    with context.begin_transaction():
        context.run_migrations()


# === Белый список таблиц, которые мигрирует облако ===
CLOUD_TABLES = {
    'cloud_file',
    'cloud_share',
    'user',                       # только для чтения/изменения индексов User
    'alembic_version_cloud',      # наша таблица версий
}


def include_object(object, name, type_, reflected, compare_to):
    """
    Alembic будет обрабатывать только таблицы из CLOUD_TABLES.
    Всё остальное (article, page, menu_item и т.д.) — игнорируется.

    reflected=True → объект есть в БД
    reflected=False → объект в модели
    """
    if type_ == 'table':
        if reflected and name not in CLOUD_TABLES:
            return False
        if not reflected and name not in CLOUD_TABLES:
            return False
    return True

def run_migrations_online():
    """Online-режим миграций (с подключением к БД)"""

    def process_revision_directives(context, revision, directives):
        """Не генерировать пустые миграции"""
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            render_as_batch=True,
            version_table='alembic_version_cloud',
            process_revision_directives=process_revision_directives,
            include_object=include_object,      # ← ДОБАВИТЬ
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()