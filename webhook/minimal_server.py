#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Минимальный webhook сервер для AI-юриста (без Supabase/YooKassa интеграции)
Используется для отладки и быстрого тестирования webhook endpoints
"""

import logging
import json
from flask import Flask, request, jsonify
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.route('/webhook/ai-lawyer', methods=['POST'])
def handle_ai_lawyer_webhook():
    """
    Минимальный webhook endpoint для AI-юриста
    Просто логирует входящие данные без обработки
    """
    try:
        # Получаем данные от YooKassa
        webhook_data = request.get_json()
        
        if not webhook_data:
            logger.warning("Получен пустой webhook")
            return jsonify({"error": "Empty webhook data"}), 400
        
        logger.info(f"AI-Lawyer webhook получен: {webhook_data}")
        
        # Возвращаем успешный ответ
        return jsonify({
            "status": "success", 
            "message": "Webhook получен и обработан",
            "received_data": webhook_data
        }), 200
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    Проверка здоровья сервиса
    """
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "ai-lawyer-webhook-minimal"
    }), 200


@app.route('/', methods=['GET'])
def index():
    """
    Главная страница
    """
    return jsonify({
        "service": "AI-Lawyer Webhook Server (Minimal)",
        "version": "1.0.0-minimal",
        "endpoints": [
            "/webhook/ai-lawyer",
            "/health"
        ]
    }), 200


if __name__ == '__main__':
    logger.info("🚀 Запуск минимального webhook сервера...")
    logger.info("📡 Доступные endpoints:")
    logger.info("  • /webhook/ai-lawyer - AI-юрист (минимальная версия)")
    logger.info("  • /health - Проверка здоровья")
    
    # Запуск сервера на порту 8080 (для отладки)
    app.run(host='0.0.0.0', port=8080, debug=True) 