# 🔗 AI-Lawyer Webhook Server

Объединенный webhook сервер для обработки платежей AI-юриста и других проектов.

## 📋 Возможности

- **Отдельные endpoints** для разных проектов
- **YooKassa интеграция** для AI-юриста
- **Автоматическая обработка** платежей и подписок
- **Health checks** и мониторинг
- **Production-ready** конфигурация
- **Масштабируемая архитектура**

## 🚀 Быстрый старт

### Разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env

# Запуск dev сервера
python webhook/deploy.py dev
```

### Продакшен

```bash
# Подготовка конфигураций
python webhook/deploy.py prod

# Следуйте инструкциям в выводе
```

## 📡 Endpoints

### AI-Lawyer (YooKassa)
- **URL**: `/webhook/ai-lawyer`
- **Method**: `POST`
- **Purpose**: Обработка платежей от YooKassa

### Другие проекты
- **URL**: `/webhook/other-project`
- **Method**: `POST`
- **Purpose**: Placeholder для других проектов

### Системные
- **URL**: `/health`
- **Method**: `GET`
- **Purpose**: Проверка здоровья сервиса

- **URL**: `/status`
- **Method**: `GET`
- **Purpose**: Детальный статус сервера

## ⚙️ Конфигурация

### Переменные окружения

```env
# YooKassa (обязательно)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Supabase (обязательно)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Дополнительно
FLASK_ENV=production
WEBHOOK_PORT=8080
```

### Gunicorn (продакшен)

```python
# gunicorn.conf.py
bind = "0.0.0.0:8080"
workers = 4
worker_class = "sync"
timeout = 30
keepalive = 2
```

### Nginx (обратный прокси)

```nginx
server {
    listen 443 ssl;
    server_name webhook.ii-photo.ru;
    
    location /webhook/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhook/ai-lawyer {
        limit_req zone=webhook burst=10 nodelay;
        proxy_pass http://127.0.0.1:8080/webhook/ai-lawyer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔐 Безопасность

### Rate Limiting

```nginx
# В nginx.conf
limit_req_zone $binary_remote_addr zone=webhook:10m rate=1r/s;

location /webhook/ai-lawyer {
    limit_req zone=webhook burst=10 nodelay;
    # ...
}
```

### SSL/TLS

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
```

### Валидация webhook

Сервер автоматически валидирует входящие webhook от YooKassa:

```python
def validate_yookassa_webhook(webhook_data):
    required_fields = ['event', 'object']
    # Проверка структуры и данных
```

## 📊 Мониторинг

### Health Check

```bash
curl https://webhook.ii-photo.ru/health
```

Ответ:
```json
{
  "status": "ok",
  "timestamp": "2024-01-20T10:30:00Z",
  "services": {
    "webhook_server": "running",
    "yookassa_client": "ok",
    "supabase_client": "ok"
  }
}
```

### Детальный статус

```bash
curl https://webhook.ii-photo.ru/status
```

### Логирование

```python
# Файлы логов
logs/access.log    # Логи доступа (nginx/gunicorn)
logs/error.log     # Логи ошибок
webhook.log        # Логи приложения
```

## 🛠️ Разработка

### Структура проекта

```
webhook/
├── server.py          # Основной Flask сервер
├── deploy.py          # Скрипт развертывания
├── README.md          # Документация
├── gunicorn.conf.py   # Конфигурация gunicorn (создается)
├── nginx.conf         # Конфигурация nginx (создается)
└── logs/              # Директория для логов
```

### Добавление нового проекта

1. Создайте новый endpoint:

```python
@app.route('/webhook/new-project', methods=['POST'])
def handle_new_project_webhook():
    try:
        webhook_data = request.get_json()
        
        # Обработка webhook
        result = process_new_project_webhook(webhook_data)
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Ошибка в New-Project webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500
```

2. Добавьте обработчик:

```python
def process_new_project_webhook(webhook_data):
    # Логика обработки
    pass
```

3. Обновите health check:

```python
"services": {
    "webhook_server": "running",
    "new_project_client": "ok"
}
```

## 🚀 Развертывание

### Systemd Service

```bash
# Создание service
sudo cp ai-lawyer-webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-lawyer-webhook

# Управление
sudo systemctl start ai-lawyer-webhook
sudo systemctl stop ai-lawyer-webhook
sudo systemctl restart ai-lawyer-webhook
sudo systemctl status ai-lawyer-webhook
```

### Docker (альтернатива)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "webhook.server:app"]
```

```bash
# Сборка и запуск
docker build -t ai-lawyer-webhook .
docker run -d -p 8080:8080 --env-file .env ai-lawyer-webhook
```

## 🔧 Troubleshooting

### Проблемы с запуском

```bash
# Проверка портов
sudo netstat -tulnp | grep :8080

# Проверка логов
journalctl -u ai-lawyer-webhook -f

# Проверка конфигурации
python -c "from webhook.server import app; print('OK')"
```

### Проблемы с webhook

```bash
# Тест webhook вручную
curl -X POST https://webhook.ii-photo.ru/webhook/ai-lawyer \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "object": {"id": "test"}}'

# Проверка логов webhook
tail -f webhook.log | grep "AI-Lawyer"
```

### Проблемы с базой данных

```bash
# Проверка подключения к Supabase
python -c "from supabase.database import supabase_client; print('DB OK')"

# Проверка таблиц
python scripts/check_database.py
```

## 📈 Производительность

### Оптимизация gunicorn

```python
# Для CPU-intensive задач
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Для I/O-intensive задач
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
```

### Мониторинг производительности

```bash
# Мониторинг CPU/Memory
htop

# Мониторинг сетевых соединений
ss -tuln | grep :8080

# Мониторинг логов в реальном времени
tail -f logs/access.log
```

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `tail -f webhook.log`
2. Проверьте статус: `curl /health`
3. Проверьте переменные окружения
4. Проверьте права доступа к файлам

---

**Webhook URL для YooKassa**: `https://webhook.ii-photo.ru/webhook/ai-lawyer` 