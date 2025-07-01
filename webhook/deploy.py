#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт развертывания webhook сервера для продакшена
Использует gunicorn для production-ready запуска
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def check_dependencies():
    """
    Проверяет наличие всех необходимых зависимостей
    """
    required_packages = [
        'flask>=3.0.0',
        'gunicorn>=21.0.0',
        'python-dotenv>=1.0.0',
        'yookassa>=3.7.0',
        'supabase>=2.10.0'
    ]
    
    print("🔍 Проверка зависимостей...")
    
    try:
        import flask
        import gunicorn
        import yookassa
        import supabase
        print("✅ Все основные зависимости установлены")
        return True
    except ImportError as e:
        print(f"❌ Отсутствует зависимость: {e}")
        print("📦 Установите зависимости: pip install -r requirements.txt")
        return False


def check_environment():
    """
    Проверяет переменные окружения
    """
    required_env_vars = [
        'YOOKASSA_SHOP_ID',
        'YOOKASSA_SECRET_KEY',
        'SUPABASE_URL',
        'SUPABASE_KEY'
    ]
    
    print("🔍 Проверка переменных окружения...")
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        print("📝 Создайте файл .env с необходимыми переменными")
        return False
    
    print("✅ Все переменные окружения настроены")
    return True


def create_gunicorn_config():
    """
    Создает конфигурацию для gunicorn
    """
    config_content = """# Gunicorn конфигурация для webhook сервера
import multiprocessing

# Сервер настройки
bind = "0.0.0.0:8080"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50

# Логирование
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Процесс
daemon = False
pidfile = "webhook.pid"
user = None
group = None
preload_app = True

# Безопасность
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
"""
    
    # Создаем директорию для логов
    os.makedirs("logs", exist_ok=True)
    
    with open("gunicorn.conf.py", "w", encoding="utf-8") as f:
        f.write(config_content)
    
    print("✅ Создана конфигурация gunicorn")


def create_systemd_service():
    """
    Создает systemd service файл
    """
    current_dir = Path.cwd()
    python_path = sys.executable
    
    service_content = f"""[Unit]
Description=AI-Lawyer Webhook Server
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory={current_dir}
Environment=PATH={current_dir}/venv/bin
ExecStart={python_path} -m gunicorn --config gunicorn.conf.py webhook.server:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = "ai-lawyer-webhook.service"
    with open(service_file, "w", encoding="utf-8") as f:
        f.write(service_content)
    
    print(f"✅ Создан systemd service файл: {service_file}")
    print(f"📋 Для установки выполните:")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print(f"   sudo systemctl daemon-reload")
    print(f"   sudo systemctl enable ai-lawyer-webhook")
    print(f"   sudo systemctl start ai-lawyer-webhook")


def create_nginx_config():
    """
    Создает конфигурацию для nginx
    """
    nginx_config = """# Nginx конфигурация для AI-Lawyer Webhook
server {
    listen 80;
    server_name webhook.ii-photo.ru;  # Замените на ваш домен
    
    # Редирект на HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name webhook.ii-photo.ru;  # Замените на ваш домен
    
    # SSL сертификаты (настройте под ваши)
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    
    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # Логирование
    access_log /var/log/nginx/webhook_access.log;
    error_log /var/log/nginx/webhook_error.log;
    
    # Основная конфигурация
    location /webhook/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Размеры буферов
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }
    
    # Health check endpoints
    location /health {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        access_log off;
    }
    
    location /status {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }
    
    # Безопасность
    location ~ /\\.ht {
        deny all;
    }
    
    # Базовая защита от DDoS
    location /webhook/ai-lawyer {
        limit_req zone=webhook burst=10 nodelay;
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Rate limiting
http {
    limit_req_zone $binary_remote_addr zone=webhook:10m rate=1r/s;
}
"""
    
    with open("nginx.conf", "w", encoding="utf-8") as f:
        f.write(nginx_config)
    
    print("✅ Создана конфигурация nginx")
    print("📋 Для применения:")
    print("   sudo cp nginx.conf /etc/nginx/sites-available/ai-lawyer-webhook")
    print("   sudo ln -s /etc/nginx/sites-available/ai-lawyer-webhook /etc/nginx/sites-enabled/")
    print("   sudo nginx -t")
    print("   sudo systemctl reload nginx")


def deploy_development():
    """
    Развертывание для разработки
    """
    print("🚀 Запуск в режиме разработки...")
    
    if not check_dependencies():
        return False
    
    if not check_environment():
        return False
    
    print("▶️  Запуск Flask dev сервера...")
    try:
        subprocess.run([
            sys.executable, 
            "webhook/server.py"
        ], check=True)
    except KeyboardInterrupt:
        print("\n⏹️  Сервер остановлен")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска: {e}")
        return False
    
    return True


def deploy_production():
    """
    Развертывание для продакшена
    """
    print("🚀 Подготовка к продакшн развертыванию...")
    
    if not check_dependencies():
        return False
    
    if not check_environment():
        return False
    
    create_gunicorn_config()
    create_systemd_service()
    create_nginx_config()
    
    print("\n✅ Файлы конфигурации созданы!")
    print("\n📋 Следующие шаги:")
    print("1. Настройте SSL сертификаты в nginx.conf")
    print("2. Установите systemd service")
    print("3. Настройте nginx конфигурацию")
    print("4. Запустите сервис: sudo systemctl start ai-lawyer-webhook")
    print("5. Проверьте статус: sudo systemctl status ai-lawyer-webhook")
    
    return True


def main():
    """
    Главная функция
    """
    print("🎯 AI-Lawyer Webhook Deployer")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python deploy.py dev     - Запуск для разработки")
        print("  python deploy.py prod    - Подготовка для продакшена")
        return
    
    mode = sys.argv[1].lower()
    
    if mode == "dev":
        deploy_development()
    elif mode == "prod":
        deploy_production()
    else:
        print("❌ Неизвестный режим. Используйте 'dev' или 'prod'")


if __name__ == "__main__":
    main() 