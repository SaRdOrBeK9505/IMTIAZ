#!/bin/bash
# ============================================================
# IMTIAZ — Production Deploy Script
# Ubuntu 22.04 | Python 3.13 | PostgreSQL | Redis | Nginx
#
# Birinchi deploy:  bash deploy.sh --setup
# Yangilanish:      bash deploy.sh
# ============================================================

set -euo pipefail

APP_DIR="/home/imtiaz/app"
VENV="$APP_DIR/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()     { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }
section() { echo -e "\n${YELLOW}══ $1 ══${NC}"; }

# ─── Birinchi marta sozlash ───────────────────────────────────────────────────
setup() {
    section "Tizim paketlarini o'rnatish"
    sudo apt-get update -q
    sudo apt-get install -y -q \
        python3.13 python3.13-venv python3-pip \
        postgresql postgresql-contrib \
        redis-server \
        nginx \
        certbot python3-certbot-nginx \
        git curl build-essential libpq-dev

    section "Foydalanuvchi yaratish"
    id -u imtiaz &>/dev/null || sudo useradd -m -s /bin/bash imtiaz
    sudo usermod -aG www-data imtiaz

    section "Papkalar yaratish"
    sudo mkdir -p $APP_DIR/logs $APP_DIR/staticfiles $APP_DIR/media
    sudo chown -R imtiaz:imtiaz $APP_DIR

    section "PostgreSQL sozlash"
    read -p "DB nomi [imtiaz_db]: "       DB_NAME;     DB_NAME=${DB_NAME:-imtiaz_db}
    read -p "DB user [imtiaz_user]: "     DB_USER;     DB_USER=${DB_USER:-imtiaz_user}
    read -s -p "DB paroli: "              DB_PASSWORD; echo
    read -p "DB host [localhost]: "       DB_HOST;     DB_HOST=${DB_HOST:-localhost}
    read -p "DB port [5432]: "            DB_PORT;     DB_PORT=${DB_PORT:-5432}

    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" 2>/dev/null || warn "User '${DB_USER}' allaqachon mavjud"
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || warn "DB '${DB_NAME}' allaqachon mavjud"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
    log "PostgreSQL tayyor: ${DB_NAME} / ${DB_USER}@${DB_HOST}:${DB_PORT}"

    echo ""
    warn "MUHIM: /home/imtiaz/app/.env faylida quyidagilarni to'ldiring:"
    echo "  DB_NAME=${DB_NAME}"
    echo "  DB_USER=${DB_USER}"
    echo "  DB_PASSWORD=${DB_PASSWORD}"
    echo "  DB_HOST=${DB_HOST}"
    echo "  DB_PORT=${DB_PORT}"
    echo "  DB_USE_SQLITE=False"

    section "Redis sozlash"
    sudo systemctl enable redis-server
    sudo systemctl start redis-server

    section "Virtual environment yaratish"
    sudo -u imtiaz python3.13 -m venv $VENV

    log "Setup tugadi. Endi 'bash deploy.sh' ni ishga tushiring."
}

# ─── Deploy ───────────────────────────────────────────────────────────────────
deploy() {
    cd $APP_DIR

    section "Git pull"
    git pull origin main
    log "Kod yangilandi"

    section "Dependencylar"
    $PIP install -q --upgrade pip
    $PIP install -q -r requirements.txt
    log "Paketlar o'rnatildi"

    section "Migrations"
    $PYTHON manage.py migrate --noinput
    log "Migrations bajarildi"

    section "Periodic tasks"
    $PYTHON manage.py setup_periodic_tasks

    section "Static fayllar"
    $PYTHON manage.py collectstatic --noinput --clear
    log "Static fayllar yig'ildi"

    section "Sog'lik tekshiruvi"
    $PYTHON manage.py check --deploy 2>&1 | grep -v "DEBUG\|HSTS\|SSL\|SECURE\|SECRET" || true

    section "Servislarni qayta ishga tushirish"
    sudo systemctl reload  imtiaz          || sudo systemctl restart imtiaz
    sudo systemctl restart imtiaz-celery
    sudo systemctl restart imtiaz-celery-beat
    sudo systemctl reload  nginx

    section "Servis holati"
    sudo systemctl is-active imtiaz         && log "Gunicorn: ishlayapti" || warn "Gunicorn: ishlamayapti"
    sudo systemctl is-active imtiaz-celery  && log "Celery: ishlayapti"   || warn "Celery: ishlamayapti"
    sudo systemctl is-active nginx          && log "Nginx: ishlayapti"    || warn "Nginx: ishlamayapti"

    log "Deploy muvaffaqiyatli tugadi!"
}

# ─── Entry point ──────────────────────────────────────────────────────────────
case "${1:-deploy}" in
    --setup) setup ;;
    *)       deploy ;;
esac
