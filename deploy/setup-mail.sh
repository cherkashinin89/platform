#!/bin/bash
# ================================================================
# deploy/setup-mail.sh — развёртывание почтового сервиса
# ================================================================
# Требования:
#   - Debian 12 / 13
#   - Пользователь deploy с sudo
#   - Заполненный .env (MAIL_*, VMAIL_*)
#   - PostgreSQL с БД myframework (или MAIL_DB_NAME)
#   - Таблицы mail_domain, mailbox (создаются миграциями mail/)
#
# Использование:
#   cd /home/deploy/apps/platform
#   sudo bash deploy/setup-mail.sh
# ================================================================

set -e  # прервать при ошибке

PLATFORM_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== PLATFORM_DIR = $PLATFORM_DIR ==="

# === 1. Проверки ===
if [ "$EUID" -ne 0 ]; then
    echo "Ошибка: скрипт должен запускаться от root (sudo)."
    exit 1
fi

if [ ! -f "$PLATFORM_DIR/.env" ]; then
    echo "Ошибка: $PLATFORM_DIR/.env не найден."
    exit 1
fi

# Загружаем .env
set -a
source "$PLATFORM_DIR/.env"
set +a

# Проверяем обязательные переменные
for var in MAIL_HOSTNAME MAIL_DOMAIN MAIL_DB_USER MAIL_DB_PASSWORD MAIL_DB_NAME VMAIL_UID VMAIL_GID VMAIL_HOME; do
    if [ -z "${!var}" ]; then
        echo "Ошибка: переменная $var не задана в .env"
        exit 1
    fi
done

echo "=== MAIL_HOSTNAME = $MAIL_HOSTNAME ==="
echo "=== MAIL_DOMAIN   = $MAIL_DOMAIN ==="
echo "=== MAIL_DB_NAME  = $MAIL_DB_NAME ==="
echo "=== VMAIL_HOME    = $VMAIL_HOME ==="

TEMPLATES_DIR="$PLATFORM_DIR/deploy/templates"

# === 2. Системные пакеты ===
echo "=== Установка пакетов ==="

# debconf: чтобы postfix не спрашивал про тип конфигурации
echo "postfix postfix/main_mailer_type select No configuration" | debconf-set-selections
echo "postfix postfix/mailname string $MAIL_HOSTNAME" | debconf-set-selections

export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y \
    postfix postfix-pgsql \
    dovecot-core dovecot-imapd dovecot-pop3d dovecot-lmtpd dovecot-pgsql dovecot-sieve \
    rspamd \
    swaks

# === 3. Пользователь vmail ===
echo "=== Пользователь vmail (uid=$VMAIL_UID, gid=$VMAIL_GID) ==="
if ! getent group vmail > /dev/null; then
    groupadd -g "$VMAIL_GID" vmail
fi
if ! getent passwd vmail > /dev/null; then
    useradd -g vmail -u "$VMAIL_UID" -d "$VMAIL_HOME" -m -s /usr/sbin/nologin vmail
fi
mkdir -p "$VMAIL_HOME"
chown -R vmail:vmail "$VMAIL_HOME"
chmod 770 "$VMAIL_HOME"

# === 4. Роль mail_reader в PostgreSQL ===
echo "=== Роль $MAIL_DB_USER в PostgreSQL ==="
sudo -u postgres psql "$MAIL_DB_NAME" << SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$MAIL_DB_USER') THEN
        CREATE ROLE $MAIL_DB_USER WITH LOGIN PASSWORD '$MAIL_DB_PASSWORD';
    ELSE
        ALTER ROLE $MAIL_DB_USER WITH PASSWORD '$MAIL_DB_PASSWORD';
    END IF;
END
\$\$;
GRANT CONNECT ON DATABASE $MAIL_DB_NAME TO $MAIL_DB_USER;
GRANT USAGE ON SCHEMA public TO $MAIL_DB_USER;
GRANT SELECT ON mail_domain TO $MAIL_DB_USER;
GRANT SELECT ON mailbox TO $MAIL_DB_USER;
GRANT UPDATE (last_login) ON mailbox TO $MAIL_DB_USER;
SQL

# === 5. Postfix ===
echo "=== Postfix: рендер шаблонов ==="
for f in main.cf pgsql-virtual-mailbox-domains.cf pgsql-virtual-mailbox-maps.cf; do
    tmp="$(mktemp)"
    sed -e "s|__MAIL_HOSTNAME__|$MAIL_HOSTNAME|g" \
        -e "s|__MAIL_DOMAIN__|$MAIL_DOMAIN|g" \
        -e "s|__MAIL_DB_USER__|$MAIL_DB_USER|g" \
        -e "s|__MAIL_DB_PASSWORD__|$MAIL_DB_PASSWORD|g" \
        -e "s|__MAIL_DB_NAME__|$MAIL_DB_NAME|g" \
        -e "s|__VMAIL_HOME__|$VMAIL_HOME|g" \
        -e "s|__VMAIL_UID__|$VMAIL_UID|g" \
        -e "s|__VMAIL_GID__|$VMAIL_GID|g" \
        "$TEMPLATES_DIR/postfix/$f" > "$tmp"
    install -o root -g root -m 0644 "$tmp" "/etc/postfix/$f"
    rm -f "$tmp"
done
# pgsql-*.cf должны быть 0640 (пароль!)
chmod 0640 /etc/postfix/pgsql-virtual-mailbox-*.cf

postfix check
systemctl restart postfix

# === 6. Dovecot ===
echo "=== Dovecot: рендер шаблонов ==="

# auth-sql.conf.ext (пароль)
tmp="$(mktemp)"
sed -e "s|__MAIL_DB_USER__|$MAIL_DB_USER|g" \
    -e "s|__MAIL_DB_PASSWORD__|$MAIL_DB_PASSWORD|g" \
    -e "s|__MAIL_DB_NAME__|$MAIL_DB_NAME|g" \
    "$TEMPLATES_DIR/dovecot/auth-sql.conf.ext" > "$tmp"
install -o root -g dovecot -m 0640 "$tmp" /etc/dovecot/conf.d/auth-sql.conf.ext
rm -f "$tmp"

# 10-mail.conf
tmp="$(mktemp)"
sed -e "s|__VMAIL_HOME__|$VMAIL_HOME|g" \
    -e "s|__VMAIL_UID__|$VMAIL_UID|g" \
    -e "s|__VMAIL_GID__|$VMAIL_GID|g" \
    "$TEMPLATES_DIR/dovecot/10-mail.conf" > "$tmp"
install -o root -g root -m 0644 "$tmp" /etc/dovecot/conf.d/10-mail.conf
rm -f "$tmp"

# Остальные без параметров — просто копируем
for f in 10-auth.conf 10-master.conf 10-ssl.conf 20-lmtp.conf dovecot.conf; do
    install -o root -g root -m 0644 "$TEMPLATES_DIR/dovecot/$f" "/etc/dovecot/conf.d/$f"
done

doveconf -n > /dev/null
systemctl restart dovecot

# === 7. Rspamd ===
echo "=== Rspamd: конфиги ==="
mkdir -p /var/lib/rspamd/dkim
chown _rspamd:_rspamd /var/lib/rspamd/dkim 2>/dev/null || true

for f in dkim_signing.conf milter_headers.conf; do
    install -o root -g root -m 0644 "$TEMPLATES_DIR/rspamd/$f" "/etc/rspamd/local.d/$f"
done

rspamadm configtest
systemctl restart rspamd

# === 8. Проверка ===
echo ""
echo "=== Проверка ==="
systemctl status postfix --no-pager | head -3
systemctl status dovecot --no-pager | head -3
systemctl status rspamd --no-pager | head -3

echo ""
echo "=== Готово! ==="
echo "Проверка: swaks --to test@$MAIL_DOMAIN --from deploy@$MAIL_DOMAIN --server 127.0.0.1"

# === Фиксация версий (чтобы apt upgrade не сломал конфиги) ===
echo "=== Фиксация версий пакетов ==="
apt-mark hold postfix postfix-pgsql postfix-mta-sts-resolver \
    dovecot-core dovecot-imapd dovecot-pop3d dovecot-lmtpd dovecot-pgsql dovecot-sieve \
    rspamd