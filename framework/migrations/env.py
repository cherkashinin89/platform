import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


# === Белый список таблиц, которые мигрирует myframework ===
FRAMEWORK_TABLES = {
    'user',
    'article',
    'page',
    'menu_item',
    'uploaded_file',
    'album',
    'photo',
    'article_authors',
    'article_albums',
    'site_settings',
    'alembic_version',
    # W3-рефакторинг: реестр использования файлов и журнал действий
    'file_usage',
    'audit_log',
    # НЕ включаем: cloud_file, cloud_share, alembic_version_cloud — это mycloud
}


def include_object(object, name, type_, reflected, compare_to):
    """
    Alembic обрабатывает только таблицы из FRAMEWORK_TABLES.
    Таблицы облака (cloud_file, cloud_share) — игнорируются.
    """
    if type_ == 'table':
        if reflected and name not in FRAMEWORK_TABLES:
            return False
        if not reflected and name not in FRAMEWORK_TABLES:
            return False
    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            include_object=include_object,
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


# === Точка входа ===
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()