# check_templates.py
import os
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
# Регистрируем фильтр, чтобы не ругался на files.html
from file_utils import human_size
env.filters['human_size_bytes'] = human_size

# Заглушки для Flask-специфичных функций
env.globals['csrf_token'] = lambda: 'dummy'
env.globals['url_for'] = lambda *a, **kw: '#'
env.globals['get_flashed_messages'] = lambda *a, **kw: []
env.globals['current_user'] = type('U', (), {
    'is_authenticated': True, 'username': 'test',
    'is_admin': True, 'id': 1,
})()
env.globals['request'] = type('R', (), {'endpoint': '', 'args': {}})()
env.globals['site_settings'] = None

errors = 0
for root, _, files in os.walk(TEMPLATE_DIR):
    for name in files:
        if not name.endswith('.html'):
            continue
        rel = os.path.relpath(os.path.join(root, name), TEMPLATE_DIR).replace('\\', '/')
        try:
            env.get_template(rel)
            print(f'OK   {rel}')
        except TemplateSyntaxError as e:
            errors += 1
            print(f'FAIL {rel}: строка {e.lineno} — {e.message}')

print()
print('Ошибок:', errors)