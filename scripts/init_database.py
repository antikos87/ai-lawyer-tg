#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для инициализации базы данных Supabase
"""

import asyncio
import logging
from db_client.database import supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """
    Инициализация базы данных
    """
    try:
        logger.info("Начинаем инициализацию базы данных...")
        
        # Проверяем соединение
        result = supabase_client.client.table('subscription_limits').select('*').execute()
        
        if result.data:
            logger.info(f"База данных уже инициализирована. Найдено {len(result.data)} тарифов.")
            
            # Показываем текущие тарифы
            for limit in result.data:
                price_rub = limit['price_kopecks'] / 100
                logger.info(f"Тариф {limit['subscription_type']}: {price_rub}₽, "
                          f"консультации: {limit['consultations_limit']}, "
                          f"документы: {limit['documents_limit']}, "
                          f"анализ: {limit['analysis_limit']}")
        else:
            logger.info("База данных пуста, требуется настройка.")
        
        logger.info("Инициализация завершена успешно!")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise


async def test_subscription_flow():
    """
    Тестирование процесса подписки
    """
    try:
        logger.info("Тестируем процесс подписки...")
        
        test_telegram_id = 12345678
        
        # Получаем пользователя
        user = await supabase_client.get_or_create_user(
            telegram_id=test_telegram_id,
            username="test_user",
            first_name="Тест"
        )
        
        logger.info(f"Создан тестовый пользователь: {user['id']}")
        
        # Проверяем статус подписки
        status = await supabase_client.get_user_subscription_status(test_telegram_id)
        logger.info(f"Статус подписки: {status}")
        
        # Создаем пробную подписку
        if not status['is_trial_used']:
            trial_sub = await supabase_client.create_trial_subscription(test_telegram_id)
            logger.info(f"Создана пробная подписка: {trial_sub['id']}")
            
            # Тестируем проверку лимитов
            can_use, usage_info = await supabase_client.check_and_log_usage(
                telegram_id=test_telegram_id,
                action_type='consultation'
            )
            
            logger.info(f"Можно использовать консультацию: {can_use}")
            logger.info(f"Информация об использовании: {usage_info}")
        
        logger.info("Тест подписки завершен успешно!")
        
    except Exception as e:
        logger.error(f"Ошибка тестирования подписки: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(init_database())
 