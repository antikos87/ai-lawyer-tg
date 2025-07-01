#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production webhook сервер для AI-юриста
Работает на отдельном порту и интегрируется с существующим nginx
"""

import logging
import json
import os
import sys
import asyncio

# Добавляем путь к проекту для импорта модулей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from datetime import datetime
from db_client.database import SupabaseClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ai-lawyer-webhook.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
app = Flask(__name__)

# Инициализация клиента базы данных
try:
    supabase_client = SupabaseClient()
    logger.info("Webhook: Supabase клиент инициализирован")
except Exception as e:
    logger.error(f"Webhook: Ошибка инициализации Supabase: {e}")
    supabase_client = None


@app.route('/webhook/ai-lawyer', methods=['POST'])
def handle_ai_lawyer_webhook():
    """
    Production endpoint для AI-юриста (YooKassa)
    """
    try:
        # Получаем данные от YooKassa
        webhook_data = request.get_json()
        
        if not webhook_data:
            logger.warning("AI-Lawyer: Получен пустой webhook от YooKassa")
            return jsonify({"error": "Empty webhook data"}), 400
        
        # Логируем полученные данные
        logger.info(f"AI-Lawyer webhook получен: {webhook_data.get('event', 'unknown')}")
        logger.debug(f"AI-Lawyer webhook data: {webhook_data}")
        
        # Базовая валидация YooKassa webhook
        if not validate_yookassa_webhook(webhook_data):
            logger.warning("AI-Lawyer: Невалидный webhook от YooKassa")
            return jsonify({"error": "Invalid webhook"}), 400
        
        # Обрабатываем webhook
        result = process_webhook_simple(webhook_data)
        
        if result['success']:
            logger.info(f"AI-Lawyer: Webhook успешно обработан - {result['message']}")
            return jsonify({"status": "success", "message": result['message']}), 200
        else:
            logger.error(f"AI-Lawyer: Ошибка обработки webhook - {result['error']}")
            return jsonify({"error": result['error']}), 500
        
    except Exception as e:
        logger.error(f"AI-Lawyer: Критическая ошибка webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500


def validate_yookassa_webhook(webhook_data):
    """
    Базовая валидация webhook от YooKassa
    """
    required_fields = ['event', 'object']
    
    for field in required_fields:
        if field not in webhook_data:
            logger.warning(f"AI-Lawyer: Отсутствует поле {field}")
            return False
    
    payment_obj = webhook_data.get('object', {})
    if not payment_obj.get('id'):
        logger.warning("AI-Lawyer: Отсутствует ID платежа")
        return False
    
    return True


def process_webhook_simple(webhook_data):
    """
    Обработка webhook с интеграцией Supabase
    """
    try:
        event_type = webhook_data.get('event')
        payment_obj = webhook_data.get('object', {})
        payment_id = payment_obj.get('id')
        status = payment_obj.get('status')
        metadata = payment_obj.get('metadata', {})
        
        telegram_id = metadata.get('telegram_id')
        subscription_type = metadata.get('subscription_type')
        
        # Логируем важную информацию
        logger.info(f"AI-Lawyer: Событие {event_type}, платеж {payment_id}, статус {status}")
        
        if telegram_id and subscription_type:
            logger.info(f"AI-Lawyer: Пользователь {telegram_id}, тариф {subscription_type}")
        
        # Обрабатываем разные типы событий
        if event_type == 'payment.succeeded':
            if telegram_id and subscription_type:
                # Активируем подписку через Supabase
                if supabase_client:
                    try:
                        # Создаем новую event loop для async операций
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Создаем платную подписку
                        subscription = loop.run_until_complete(
                            supabase_client.create_paid_subscription(
                                telegram_id=int(telegram_id),
                                subscription_type=subscription_type,
                                payment_id=payment_id
                            )
                        )
                        
                        # Обновляем статус платежа
                        loop.run_until_complete(
                            supabase_client.update_payment_status(payment_id, 'succeeded')
                        )
                        
                        loop.close()
                        
                        message = f"Подписка {subscription_type} успешно активирована для пользователя {telegram_id}"
                        logger.info(f"AI-Lawyer: {message}")
                        
                        return {"success": True, "message": message}
                    except Exception as e:
                        logger.error(f"AI-Lawyer: Ошибка активации подписки: {e}")
                        return {"success": False, "error": f"Ошибка активации: {e}"}
                else:
                    # Fallback если Supabase недоступен
                    message = f"Платеж {payment_id} успешен (Supabase недоступен). Пользователь: {telegram_id}, тариф: {subscription_type}"
                    logger.warning(f"AI-Lawyer: {message}")
                    return {"success": True, "message": message}
            else:
                error = f"Недостаточно данных для активации подписки: {payment_id}"
                logger.error(f"AI-Lawyer: {error}")
                return {"success": False, "error": error}
                
        elif event_type == 'payment.canceled':
            message = f"Платеж {payment_id} отменен"
            logger.info(f"AI-Lawyer: {message}")
            return {"success": True, "message": message}
            
        elif event_type == 'refund.succeeded':
            message = f"Возврат по платежу {payment_id} успешен"
            logger.info(f"AI-Lawyer: {message}")
            return {"success": True, "message": message}
            
        elif event_type == 'payment.waiting_for_capture':
            message = f"Платеж {payment_id} ожидает подтверждения"
            logger.info(f"AI-Lawyer: {message}")
            return {"success": True, "message": message}
            
        else:
            message = f"Обработано неизвестное событие {event_type}"
            logger.warning(f"AI-Lawyer: {message}")
            return {"success": True, "message": message}
        
    except Exception as e:
        error = f"Ошибка обработки webhook: {e}"
        logger.error(f"AI-Lawyer: {error}")
        return {"success": False, "error": error}


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check для мониторинга
    """
    return jsonify({
        "status": "ok",
        "service": "ai-lawyer-webhook",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200


@app.route('/status', methods=['GET'])
def status_check():
    """
    Детальный статус сервиса
    """
    return jsonify({
        "service": "AI-Lawyer Webhook Server",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "webhook": "/webhook/ai-lawyer",
            "health": "/health",
            "status": "/status"
        },
        "yookassa_url": "https://webhook.ii-photo.ru/webhook/ai-lawyer"
    }), 200


@app.route('/', methods=['GET'])
def index():
    """
    Информационная страница
    """
    return jsonify({
        "service": "AI-Lawyer Webhook Server",
        "description": "Обработка платежей YooKassa для AI-юриста",
        "endpoints": [
            "/webhook/ai-lawyer - Webhook для YooKassa",
            "/health - Health check",
            "/status - Статус сервиса"
        ],
        "external_url": "https://webhook.ii-photo.ru/webhook/ai-lawyer"
    }), 200


if __name__ == '__main__':
    # Настройки для production
    port = int(os.environ.get('PORT', 8081))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info("🚀 Запуск AI-Lawyer webhook сервера...")
    logger.info(f"📡 Порт: {port}")
    logger.info(f"🔗 Внешний URL: https://webhook.ii-photo.ru/webhook/ai-lawyer")
    logger.info(f"🏥 Health check: http://localhost:{port}/health")
    
    # Запуск сервера
    app.run(
        host='127.0.0.1',  # Только локальный доступ
        port=port,
        debug=debug,
        threaded=True
    ) 