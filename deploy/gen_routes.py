#!/usr/bin/env python3
"""Генератор реестра эндпоинтов cloud и framework -> docs/routes.md.

Запускается из корня platform. Каждое приложение — в отдельном процессе
(в своём venv), чтобы не конфликтовали db/app. Результат — Markdown-таблицы.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PLATFORM, 'docs', 'routes.md')
PROBE = os.path.join(PLATFORM, 'deploy', '_routes_probe.py')
NL = chr(10)


def collect(project_dir):
    """Запускает пробник в venv сервиса и возвращает список маршрутов."""
    venv_py = os.path.join(project_dir, 'venv', 'bin', 'python')
    if not os.path.exists(venv_py):
        venv_py = sys.executable
    res = subprocess.run([venv_py, PROBE], cwd=project_dir,
                         capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise SystemExit('Не удалось собрать маршруты в ' + project_dir)
    return json.loads(res.stdout)


def render(services):
    """Формирует Markdown-содержимое docs/routes.md."""
    try:
        commit = subprocess.run(['git', '-C', PLATFORM, 'rev-parse', '--short', 'HEAD'],
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = '?'
    lines = []
    lines.append('# Реестр эндпоинтов')
    lines.append('')
    lines.append('Сгенерировано: ' + datetime.now().strftime('%Y-%m-%d %H:%M') + ', коммит ' + chr(96) + commit + chr(96) + '.')
    lines.append('')
    lines.append('**НЕ ПРАВИТЬ РУКАМИ** — генерируется deploy/gen_routes.py.')
    for svc, routes in services:
        lines.append('')
        lines.append('## ' + svc)
        lines.append('')
        lines.append('| Метод | Путь | Endpoint | Категория | Назначение | Файл:функция |')
        lines.append('|---|---|---|---|---|---|')
        routes.sort(key=lambda r: (r['path'], ','.join(r['methods'])))
        for r in routes:
            methods = ', '.join(r['methods'])
            doc = r['purpose'].replace('|', '/')
            lines.append('| ' + methods + ' | ' + chr(96) + r['path'] + chr(96) +
                         ' | ' + r['endpoint'] + ' | ' + r['category'] + ' | ' + doc +
                         ' | ' + chr(96) + r['source'] + chr(96) + ' |')
    return NL.join(lines) + NL


def main():
    services = []
    for name in ('framework', 'cloud'):
        pdir = os.path.join(PLATFORM, name)
        routes = collect(pdir)
        services.append((name, routes))
    content = render(services)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    total = sum(len(r) for _, r in services)
    print('written: ' + OUT + ' (' + str(total) + ' routes)')


if __name__ == '__main__':
    main()
