#!/usr/bin/env python3
"""Пробник маршрутов: импортирует app и печатает JSON со списком маршрутов.

Запускается из deploy/gen_routes.py в venv конкретного сервиса.
"""
import inspect
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from app import app  # noqa: E402  (создаёт Flask-приложение)


def category_for(path, endpoint, doc, src_text):
    """Эвристика категории: internal/wopi/admin/auth/public."""
    ep = (endpoint or "").lower()
    text = src_text or ''
    if 'internal' in ep or 'X-Internal-Key' in (doc or '') or '/internal' in (path or ''):
        return 'internal'
    if '/wopi' in (path or ''):
        return 'wopi'
    if '/admin' in (path or '') or 'admin_required' in (doc or '') or 'admin_required' in text:
        return 'admin'
    if 'login_required' in (doc or '') or 'login_required' in text:
        return 'auth'
    return 'public'


def main():
    out = []
    seen = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        key = (rule.rule, rule.endpoint)
        if key in seen:
            continue
        seen.add(key)
        view = app.view_functions.get(rule.endpoint)
        methods = sorted(m for m in rule.methods if m not in ('HEAD', 'OPTIONS'))
        doc = (view.__doc__ or '').strip() if view else ''
        purpose = doc.splitlines()[0].strip() if doc else ''
        try:
            src_text = inspect.getsource(view) if view else ''
        except (OSError, TypeError):
            src_text = ''
        view = inspect.unwrap(view) if view else view
        if view and hasattr(view, '__code__'):
            fname = os.path.basename(view.__code__.co_filename)
            src = fname + ':' + view.__code__.co_name
        else:
            src = ''
        out.append({
            'methods': methods,
            'path': rule.rule,
            'endpoint': rule.endpoint,
            'category': category_for(rule.rule, rule.endpoint, doc, src_text),
            'purpose': purpose,
            'source': src,
        })
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
