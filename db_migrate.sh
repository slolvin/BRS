#!/bin/bash

# --- НАСТРОЙКИ СЕРВЕРА ---
SERVER_USER="root"
SERVER_IP="123.45.67.89"              # Измените на IP вашего VPS
PROJECT_DIR="/var/www/brs_project"    # Папка проекта на сервере

echo "🔄 Запуск ручной миграции БД на удаленном сервере $SERVER_IP..."

ssh ${SERVER_USER}@${SERVER_IP} << 'EOF'
  cd /var/www/brs_project || { echo "❌ Ошибка: Папка проекта не найдена!"; exit 1; }

  if [ "$(docker compose ps -q web)" ]; then
    echo "🔍 1. Текущий статус миграций на сервере:"
    docker compose exec -T web flask db current

    echo "🗄️ 2. Применение новых миграций (flask db upgrade)..."
    docker compose exec -T web flask db upgrade

    echo "✅ Миграции успешно применены!"
  else
    echo "❌ Ошибка: Контейнер приложения (web) не запущен. Сначала запустите деплой."
    exit 1
  fi
EOF