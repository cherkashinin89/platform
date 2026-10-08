# platform

Монорепозиторий экосистемы:
- core — общий пакет (модели, auth, утилиты, шаблоны, CSS)
- framework — сайт + админка (контент, галерея, файлы)
- cloud — облачное хранилище (папки, файлы, шары, квоты)
- mail — почта (заготовка, разработка в будущем)
- deploy — общие конфиги развёртывания

## Разработка

Каждый сервис имеет собственный venv и requirements.txt.
Общий .env в корне — единый SECRET_KEY для SSO.

Установка core в venv каждого проекта:

    cd framework
    source venv/bin/activate
    pip install -e ../core

## Развёртывание

См. deploy/setup.sh.

## История

Монорепо создано в октябре 2026 объединением myframework и mycloud.
