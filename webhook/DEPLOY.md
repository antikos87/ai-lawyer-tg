# 🚀 Быстрое развертывание AI-Lawyer Webhook

## 📋 Что создано

✅ **Отдельный endpoint**: `/webhook/ai-lawyer` для AI-юриста  
✅ **Объединенный сервер**: Flask приложение с несколькими проектами  
✅ **Production конфиги**: Gunicorn, systemd, nginx  
✅ **Автодеплой скрипты**: Один команда для запуска  

## ⚡ Быстрый старт

### 1. Для разработки
```bash
# Запуск dev сервера
cd webhook/
python deploy.py dev
```

### 2. Для продакшена
```bash
# Подготовка конфигураций
python webhook/deploy.py prod

# Установка сервиса
sudo cp ai-lawyer-webhook.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-lawyer-webhook
sudo systemctl start ai-lawyer-webhook
```

### 3. Интеграция с nginx
```bash
# Добавьте блоки из nginx-integration.conf в существующую конфигурацию
# webhook.ii-photo.ru уже настроен, нужно только добавить:

location /webhook/ai-lawyer {
    proxy_pass http://127.0.0.1:8080/webhook/ai-lawyer;
    # ... (см. nginx-integration.conf)
}

# Перезагрузка nginx
sudo nginx -t
sudo systemctl reload nginx
```

## 📡 Endpoints

| URL | Назначение |
|-----|------------|
| `https://webhook.ii-photo.ru/webhook/ai-lawyer` | **YooKassa платежи AI-юриста** |
| `https://webhook.ii-photo.ru/webhook/ai-lawyer/health` | Health check |
| `https://webhook.ii-photo.ru/webhook/ai-lawyer/status` | Статус сервера |

## 🔧 Управление сервисом

```bash
# Статус
sudo systemctl status ai-lawyer-webhook

# Перезапуск
sudo systemctl restart ai-lawyer-webhook

# Логи
journalctl -u ai-lawyer-webhook -f

# Логи webhook
tail -f webhook.log
```

## ⚙️ Переменные окружения

Обязательные в `.env`:
```env
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## 🎯 YooKassa настройка

В личном кабинете YooKassa:

**Webhook URL**: `https://webhook.ii-photo.ru/webhook/ai-lawyer`

**События для подписки**:
- ✅ `payment.succeeded` (обязательно)
- ✅ `payment.canceled` (обязательно)  
- ✅ `refund.succeeded` (обязательно)
- ⚪ `payment.waiting_for_capture` (опционально)

## 🔍 Проверка работы

```bash
# Health check
curl https://webhook.ii-photo.ru/webhook/ai-lawyer/health

# Тест webhook (замените данными из YooKassa)
curl -X POST https://webhook.ii-photo.ru/webhook/ai-lawyer \
  -H "Content-Type: application/json" \
  -d '{
    "event": "payment.succeeded",
    "object": {
      "id": "test-payment-id",
      "status": "succeeded",
      "metadata": {
        "telegram_id": "123456789",
        "subscription_type": "basic"
      }
    }
  }'
```

## 🆘 Проблемы?

1. **Сервер не запускается**: `journalctl -u ai-lawyer-webhook -f`
2. **Nginx ошибки**: `tail -f /var/log/nginx/ai_lawyer_error.log`
3. **Webhook не работает**: `tail -f webhook.log | grep "AI-Lawyer"`
4. **База данных**: `python -c "from supabase.database import supabase_client; print('OK')"`

---

**Готово!** Webhook сервер создан и готов к использованию на `https://webhook.ii-photo.ru/webhook/ai-lawyer` 