# deploy — развёртывание экосистемы platform

Общие конфиги для развёртывания `framework` и `cloud` на сервере.

## Структура

    deploy/
    ├── README.md             ← этот файл
    ├── setup.sh              ← скрипт разворачивания с нуля
    ├── env.example           ← шаблон .env
    ├── nginx/
    │   ├── framework.conf
    │   └── cloud.conf
    ├── systemd/
    │   ├── framework.service
    │   └── cloud.service
    └── sudoers/
        ├── framework-restart     ← перезапуск сервиса из админки
        ├── framework-mount       ← mount/unmount внешнего диска
        └── cloud-restart         ← перезапуск облака из админки

## Развёртывание с нуля

См. `setup.sh`. Кратко:

    # 1. Клонировать репозиторий
    cd /home/deploy/apps
    git clone git@github.com:cherkashinin89/platform.git
    cd platform

    # 2. Скопировать .env и заполнить
    cp deploy/env.example .env
    nano .env
    chmod 600 .env

    # 3. Запустить setup.sh (создаст venv, установит зависимости,
    #    настроит nginx, systemd, sudoers)
    sudo SERVICE_USER=deploy bash deploy/setup.sh

## Ручное развёртывание (если setup.sh не подходит)

### Framework

    cd platform/framework
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e ../core

### Cloud

    cd platform/cloud
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e ../core

### Nginx

    sudo cp deploy/nginx/framework.conf /etc/nginx/sites-available/framework
    sudo cp deploy/nginx/cloud.conf /etc/nginx/sites-available/cloud
    sudo ln -s /etc/nginx/sites-available/framework /etc/nginx/sites-enabled/
    sudo ln -s /etc/nginx/sites-available/cloud /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl reload nginx

### Systemd

    sudo cp deploy/systemd/framework.service /etc/systemd/system/
    sudo cp deploy/systemd/cloud.service /etc/systemd/system/

    # Подставить пользователя
    sudo sed -i "s/__SERVICE_USER__/deploy/g" /etc/systemd/system/framework.service
    sudo sed -i "s/__SERVICE_USER__/deploy/g" /etc/systemd/system/cloud.service

    sudo systemctl daemon-reload
    sudo systemctl enable --now framework cloud

### Sudoers

    sudo cp deploy/sudoers/framework-restart /etc/sudoers.d/
    sudo cp deploy/sudoers/framework-mount /etc/sudoers.d/
    sudo cp deploy/sudoers/cloud-restart /etc/sudoers.d/

    # Подставить пользователя
    sudo sed -i "s/__SERVICE_USER__/deploy/g" /etc/sudoers.d/framework-restart
    sudo sed -i "s/__SERVICE_USER__/deploy/g" /etc/sudoers.d/framework-mount
    sudo sed -i "s/__SERVICE_USER__/deploy/g" /etc/sudoers.d/cloud-restart

    sudo chmod 0440 /etc/sudoers.d/framework-restart
    sudo chmod 0440 /etc/sudoers.d/framework-mount
    sudo chmod 0440 /etc/sudoers.d/cloud-restart
    sudo chown root:root /etc/sudoers.d/framework-* /etc/sudoers.d/cloud-*

    sudo visudo -c

## Проверка

    # Сервисы
    sudo systemctl status framework cloud

    # Порты
    curl -I http://127.0.0.1:5000/
    curl -I http://127.0.0.1:5002/

    # Через Nginx
    curl -I http://127.0.0.1/
    curl -I http://127.0.0.1:5001/

## Логи

    sudo journalctl -u framework -f
    sudo journalctl -u cloud -f

    sudo tail -f /var/log/nginx/framework_error.log
    sudo tail -f /var/log/nginx/cloud_error.log

## Обновление

    cd /home/deploy/apps/platform
    git pull
    # Если менялись зависимости:
    cd framework && source venv/bin/activate && pip install -r requirements.txt && pip install -e ../core
    cd ../cloud && source venv/bin/activate && pip install -r requirements.txt && pip install -e ../core
    # Перезапуск
    sudo systemctl restart framework cloud

## Архитектура

- `core/` — общий пакет (модели, auth, extensions, config, шаблоны, CSS, утилиты)
- `framework/` — сайт + админка (порт 5000)
- `cloud/` — облачное хранилище (порт 5002)
- `mail/` — почта (заготовка)

См. также главный `README.md` в корне.