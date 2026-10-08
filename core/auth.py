# core/auth.py - Декораторы для проверки ролей (общие)
#
# Иерархия ролей:
#   viewer  <  user  <  editor  <  admin
#
# Декораторы:
#   @admin_required        — только admin
#   @editor_required       — admin + editor
#   @user_required         — admin + editor + user
#   @role_required(*roles) — явно указанные роли
from functools import wraps
from flask import abort, redirect, url_for, flash, request, jsonify, current_app
from flask_login import current_user


def _deny_access():
    """
    Обработка отказа в доступе.

    Для AJAX/JSON — 403 с JSON.
    Для обычных — редирект с flash-сообщением.

    Куда редиректить — определяется наличием эндпоинта
    'admin_dashboard' в приложении:
      - есть (framework) → туда для admin
      - нет (cloud)      → на 'index'
    """
    wants_json = (
        request.path.startswith('/admin/api/')
        or request.path.startswith('/api/')
        or request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )

    if wants_json:
        return jsonify({'ok': False, 'error': 'Доступ запрещён'}), 403

    flash('Недостаточно прав для доступа к этому разделу.', 'danger')

    if current_user.is_authenticated:
        # Ищем домашний эндпоинт для админа
        if 'admin_dashboard' in current_app.view_functions:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    return redirect(url_for('login'))


def role_required(*allowed_roles):
    """Декоратор: пропускает пользователей с ролью из allowed_roles."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))

            if current_user.role not in allowed_roles:
                return _deny_access()

            return f(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(f):
    """Только для роли admin."""
    return role_required('admin')(f)


def editor_required(f):
    """Для editor и admin (управление контентом)."""
    return role_required('editor', 'admin')(f)


def user_required(f):
    """Для user, editor, admin (облако, почта)."""
    return role_required('user', 'editor', 'admin')(f)
