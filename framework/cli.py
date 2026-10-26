"""CLI-команды framework."""
import click
from flask.cli import with_appcontext

from core.extensions import db
from core.models import User


@click.command('create-admin')
@click.option('--username', prompt=True, help='Логин администратора')
@click.option('--password', prompt=True, hide_input=True,
              confirmation_prompt=True, help='Пароль')
@with_appcontext
def create_admin(username, password):
    """Создать администратора (интерактивно)."""
    if User.query.filter_by(username=username).first():
        click.echo(f'Пользователь {username} уже существует')
        return

    admin = User(
        username=username,
        email=f'{username}@example.com',
        role='admin',
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f'Создан администратор: {username}')