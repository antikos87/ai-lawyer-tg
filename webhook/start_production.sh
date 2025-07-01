#!/bin/bash
# Скрипт запуска AI-Lawyer webhook сервера в production

set -e

# Настройки
PROJECT_DIR="/home/aibot/projects/ai-lawyer-tg"
VENV_DIR="$PROJECT_DIR/venv"
WEBHOOK_SCRIPT="$PROJECT_DIR/webhook/production_server.py"
PID_FILE="/var/run/ai-lawyer-webhook.pid"
LOG_FILE="/var/log/ai-lawyer-webhook.log"
PORT=8081

# Функции
start_server() {
    echo "🚀 Запуск AI-Lawyer webhook сервера..."
    
    # Проверяем что сервер не запущен
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "❌ Сервер уже запущен (PID: $(cat $PID_FILE))"
        exit 1
    fi
    
    # Переходим в директорию проекта
    cd "$PROJECT_DIR"
    
    # Активируем виртуальное окружение и запускаем
    source "$VENV_DIR/bin/activate"
    
    # Запускаем сервер в фоне
    nohup python3 "$WEBHOOK_SCRIPT" > "$LOG_FILE" 2>&1 &
    
    # Сохраняем PID
    echo $! > "$PID_FILE"
    
    echo "✅ Сервер запущен (PID: $!)"
    echo "📡 URL: https://webhook.ii-photo.ru/webhook/ai-lawyer"
    echo "🏥 Health: http://localhost:$PORT/health"
    echo "📝 Лог: $LOG_FILE"
}

stop_server() {
    echo "⏹️  Остановка AI-Lawyer webhook сервера..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo "✅ Сервер остановлен"
        else
            echo "⚠️  Процесс с PID $PID не найден"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  PID файл не найден"
    fi
}

restart_server() {
    echo "🔄 Перезапуск AI-Lawyer webhook сервера..."
    stop_server
    sleep 2
    start_server
}

status_server() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        PID=$(cat "$PID_FILE")
        echo "✅ Сервер работает (PID: $PID)"
        echo "📡 URL: https://webhook.ii-photo.ru/webhook/ai-lawyer"
        echo "🏥 Health check:"
        curl -s "http://localhost:$PORT/health" | python3 -m json.tool
    else
        echo "❌ Сервер не запущен"
        exit 1
    fi
}

logs_server() {
    echo "📝 Последние логи AI-Lawyer webhook сервера:"
    tail -f "$LOG_FILE"
}

# Обработка аргументов
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status_server
        ;;
    logs)
        logs_server
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Команды:"
        echo "  start   - Запустить сервер"
        echo "  stop    - Остановить сервер"
        echo "  restart - Перезапустить сервер"
        echo "  status  - Статус сервера"
        echo "  logs    - Показать логи"
        echo ""
        echo "Webhook URL: https://webhook.ii-photo.ru/webhook/ai-lawyer"
        exit 1
        ;;
esac 