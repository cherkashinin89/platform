#!/bin/bash
# ================================================================
# deploy/setup.sh — развёртывание platform (framework + cloud)
# ================================================================
# Требования:
#   - Debian 12 / 13
#   - Пользователь deploy с sudo
#   - git, python3, python3-venv
#
# Использование:
#   cd /home/deploy/apps/platform
#   cp deploy/env.example .env
#   nano .env
#   chmod 600 .env
#   sudo SERVICE_USER=deploy bash deploy/setup.sh
# ================================================================

set -e  # прервать при ошибке

PLATFORM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"

echo "=== SERVICE_USER = $SERVICE_USER ==="
echo "=== PLATFORM_DIR = $PLATFORM_DIR ==="

# === 1. Проверки ===
if [ ! -f "$PLATFORM_DIR/.env" ]; then
    echo "Ошибка: $PLATFORM_DIR/.env не найден."
    echo "Скопируйте deploy/env.example в .env и заполните."
    exit 1
fi

if [ ! -d "$PLATFORM_DIR/core" ] || [ ! -d "$PLATFORM_DIR/framework" ] || [ ! -d "$PLATFORM_DIR/cloud" ]; then
    echo "Ошибка: не найдены папки core/, framework/, cloud/."
    exit 1
fi

# === 2. Системные пакеты ===
echo "=== Установка системных пакетов ==="
sudo apt update
sudo apt install -y \
    python3 python3-venv python3-pip python3-dev \
    nginx \
    git \
    acl \
    libffi-dev libssl-dev \
    build-essential

# === 3. ACL для Nginx (доступ к /home/deploy/) ===
echo "=== ACL для Nginx ==="
# Nginx-воркер (www-data) не может пройти в /home/<user> (700)
# Даём права на исполнение для www-data
sudo setfacl -m g:www-data:x "/home/$SERVICE_USER" 2>/dev/null || \
    echo "  (setfacl не сработал — пропускаем, может быть не нужно)"

# === 4. Виртуальные окружения ===
for project in framework cloud; do
    echo "=== Создание venv для $project ==="
    VENV_DIR="$PLATFORM_DIR/$project/venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$PLATFORM_DIR/$project/requirements.txt"
    pip install -e "$PLATFORM_DIR/core"
    deactivate
done

# === 5. Миграции БД (один раз — в framework) ===
echo "=== Применение миграций ==="
cd "$PLATFORM_DIR/framework"
source venv/bin/activate
flask db upgrade
deactivate

# === 6. Nginx ===
echo "=== Настройка Nginx ==="
sudo rm -f /etc/nginx/sites-enabled/default
for project in framework cloud; do
    sudo cp "$PLATFORM_DIR/deploy/nginx/$project.conf" "/etc/nginx/sites-available/$project"
    sudo ln -sf "/etc/nginx/sites-available/$project" "/etc/nginx/sites-enabled/$project"
done
sudo nginx -t
sudo systemctl reload nginx

# === 7. systemd ===
echo "=== Настройка systemd ==="
for project in framework cloud; do
    tmp_service="$(mktemp)"
    sed "s|__SERVICE_USER__|$SERVICE_USER|g" \
        "$PLATFORM_DIR/deploy/systemd/$project.service" > "$tmp_service"
    sudo cp "$tmp_service" "/etc/systemd/system/$project.service"
    rm -f "$tmp_service"
done
sudo systemctl daemon-reload
for project in framework cloud; do
    sudo systemctl enable "$project"
    sudo systemctl restart "$project"
done

# === 8. sudoers ===
echo "=== Настройка sudoers ==="
for f in "$PLATFORM_DIR/deploy/sudoers/"*; do
    name=$(basename "$f")
    tmp_sudoers="$(mktemp)"
    sed "s|__SERVICE_USER__|$SERVICE_USER|g" "$f" > "$tmp_sudoers"
    sudo cp "$tmp_sudoers" "/etc/sudoers.d/$name"
    sudo chmod 0440 "/etc/sudoers.d/$name"
    sudo chown root:root "/etc/sudoers.d/$name"
    rm -f "$tmp_sudoers"
done
sudo visudo -c

# === 9. Проверка ===
echo "=== Проверка ==="
for project in framework cloud; do
    echo "--- $project ---"
    sudo systemctl status "$project" --no-pager | head -5
done

echo ""
echo "=== Готово! ==="
echo "Framework:  sudo systemctl status framework"
echo "Cloud:      sudo systemctl status cloud"
echo "Логи:       sudo journalctl -u framework -f"
echo "            sudo journalctl -u cloud -f"
echo "Сайт:       http://<IP или домен>/"
echo "Облако:     http://<IP или домен>:5001/"