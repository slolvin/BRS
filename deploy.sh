#!/bin/bash

# --- НАСТРОЙКИ СЕРВЕРА ---
SERVER_USER="root"
SERVER_IP="123.45.67.89"
PROJECT_DIR="/var/www/brs_project"
DOMAIN="yourdomain.com"
EMAIL="your-email@gmail.com"

echo "🚀 Запуск деплоя BRS с бэкапом БД на сервер $SERVER_IP..."

ssh ${SERVER_USER}@${SERVER_IP} << 'EOF'
  cd /var/www/brs_project || { echo "❌ Ошибка: Папка проекта не найдена!"; exit 1; }

  # Шаг 1. Создаем бэкап базы данных ПЕРЕД обновлением кода
  if [ "$(docker compose ps -q db)" ]; then
    echo "💾 Контейнер базы данных активен. Создаем резервную копию..."
    mkdir -p backups
    BACKUP_NAME="backups/backup_$(date +%Y-%m-%d_%H-%M-%S).sql"

    DB_USER=$(grep POSTGRES_USER .env | cut -d '=' -f2)
    DB_NAME=$(grep POSTGRES_DB .env | cut -d '=' -f2)

    docker compose exec -T db pg_dump -U ${DB_USER} ${DB_NAME} > ${BACKUP_NAME}
    echo "✅ Бэкап успешно сохранен: ${BACKUP_NAME}"
    find backups/ -type f -name "*.sql" -mtime +30 -delete
  else
    echo "⚠️ Контейнер БД не запущен. Пропускаем бэкап."
  fi

  # Шаг 2. Обновляем код из Git
  echo "📥 Обновляем код из Git..."
  git pull origin main

  # Шаг 3. Логика управления SSL-сертификатами Let's Encrypt
  if [ -d "/var/lib/docker/volumes/brs_project_certbot_etc/_data/live/yourdomain.com" ]; then
    echo "✅ SSL-сертификаты уже существуют. Применяем стандартный запуск..."
    cp nginx.prod.conf nginx.conf
    docker compose -f compose.yaml -f docker-compose.prod.yml up --build -d
  else
    echo "🔒 Первичный запуск: Сертификаты не найдены. Выпускаем SSL..."
    cat << 'NGINX_TEMPLATE' > nginx.conf
server {
    listen 80;
    server_name yourdomain.com ://yourdomain.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
}
NGINX_TEMPLATE

    docker compose -f compose.yaml -f docker-compose.prod.yml up -d nginx certbot
    docker compose -f compose.yaml -f docker-compose.prod.yml run --rm certbot certonly --webroot --webroot-path=/var/www/certbot --email your-email@gmail.com --agree-tos --no-eff-email -d yourdomain.com -d ://yourdomain.com

    cp nginx.prod.conf nginx.conf
    docker compose -f compose.yaml -f docker-compose.prod.yml up --build -d
  fi

  # Шаг 4. Наводим порядок
  echo "🧹 Очистка старых Docker-образов..."
  docker image prune -f

  echo "🎉 Деплой кода успешно завершен!"
EOF