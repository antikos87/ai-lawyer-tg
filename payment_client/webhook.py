#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook обработчик для YooKassa
"""

import logging
import json
from typing import Dict, Any
from flask import Flask, request, jsonify

from payment_client.client import yookassa_client
from db_client.database import supabase_client

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/webhook/yookassa', methods=['POST'])
async def handle_yookassa_webhook():
    """
    Обработчик webhook от YooKassa
    """
    try:
        # Получаем данные от YooKassa
        webhook_data = request.get_json()
        
        if not webhook_data:
            logger.warning("Получен пустой webhook от YooKassa")
            return jsonify({"error": "Empty webhook data"}), 400
        
        logger.info(f"Получен webhook от YooKassa: {webhook_data.get('event', 'unknown')}")
        
        # Обрабатываем webhook
        processed_data = await yookassa_client.process_webhook(webhook_data)
        
        event_type = processed_data['event_type']
        payment_id = processed_data['payment_id']
        status = processed_data['status']
        telegram_id = processed_data.get('telegram_id')
        subscription_type = processed_data.get('subscription_type')
        
        logger.info(f"Обработан webhook: {event_type}, платеж {payment_id}, статус {status}")
        
        # Обрабатываем разные типы событий
        if event_type == 'payment.succeeded':
            await handle_payment_success(
                payment_id=payment_id,
                telegram_id=int(telegram_id) if telegram_id else None,
                subscription_type=subscription_type
            )
            
        elif event_type == 'payment.canceled':
            await handle_payment_cancellation(payment_id)
            
        elif event_type == 'payment.waiting_for_capture':
            # Автоматически подтверждаем платеж
            logger.info(f"Платеж {payment_id} ожидает подтверждения")
            
        # Обновляем статус платежа в базе
        await supabase_client.update_payment_status(payment_id, status)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook YooKassa: {e}")
        return jsonify({"error": "Internal server error"}), 500


async def handle_payment_success(payment_id: str, telegram_id: int, subscription_type: str):
    """
    Обработка успешного платежа
    """
    try:
        if not telegram_id or not subscription_type:
            logger.error(f"Недостаточно данных для создания подписки: {payment_id}")
            return
        
        # Создаем подписку
        subscription = await supabase_client.create_paid_subscription(
            telegram_id=telegram_id,
            subscription_type=subscription_type,
            payment_id=payment_id
        )
        
        logger.info(f"Создана подписка {subscription_type} для пользователя {telegram_id} по платежу {payment_id}")
        
        # TODO: Отправить уведомление пользователю в Telegram
        # await send_subscription_activation_notification(telegram_id, subscription_type)
        
    except Exception as e:
        logger.error(f"Ошибка создания подписки по платежу {payment_id}: {e}")


async def handle_payment_cancellation(payment_id: str):
    """
    Обработка отмены платежа
    """
    try:
        logger.info(f"Платеж {payment_id} отменен")
        
        # TODO: Уведомить пользователя об отмене
        
    except Exception as e:
        logger.error(f"Ошибка обработки отмены платежа {payment_id}: {e}")


@app.route('/health', methods=['GET'])
def health_check():
    """
    Проверка здоровья сервиса
    """
    return jsonify({"status": "ok", "service": "ai-lawyer-webhook"}), 200


if __name__ == '__main__':
    # Для разработки
    app.run(host='0.0.0.0', port=8080, debug=True) 