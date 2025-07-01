# 🚀 AI-Lawyer Webhook - Быстрый старт

## 🎯 **Цель**
Добавить `https://webhook.ii-photo.ru/webhook/ai-lawyer` БЕЗ нарушения ii-photo.

## ⚡ **3 простых шага**

### 1. Запуск сервера
```bash
./webhook/start_production.sh start
./webhook/start_production.sh status  # ✅ Проверка
```

### 2. Nginx конфиг
Добавить в **существующий** server блок для `webhook.ii-photo.ru`:
```nginx
location /webhook/ai-lawyer {
    proxy_pass http://127.0.0.1:8081/webhook/ai-lawyer;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    access_log /var/log/nginx/ai_lawyer_access.log;
    limit_req zone=webhook burst=20 nodelay;
}
```

### 3. Применить
```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 🎯 **YooKassa**
- **URL**: `https://webhook.ii-photo.ru/webhook/ai-lawyer`
- **События**: `payment.succeeded`, `payment.canceled`, `refund.succeeded`

## ✅ **Проверка**
```bash
curl https://webhook.ii-photo.ru/webhook/ai-lawyer/health
```

## 🛠️ **Управление**
```bash
./webhook/start_production.sh {start|stop|restart|status|logs}
```

## 🔒 **Безопасность**
- ii-photo: `/webhook` → не затронут ✅
- AI-юрист: `/webhook/ai-lawyer` → порт 8081 ⭐

## 🧪 **Отладка (локально)**
Для тестирования без Supabase/YooKassa:
```bash
python3 webhook/minimal_server.py  # Порт 8080
```

**Готово!** Webhook работает на `https://webhook.ii-photo.ru/webhook/ai-lawyer` 