#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация для AI-юрист Telegram Bot
Содержит токены, ключи API и настройки
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE')

# GigaChat API
GIGACHAT_CREDENTIALS: str = os.getenv('GIGACHAT_CREDENTIALS', 'YOUR_GIGACHAT_CREDENTIALS_HERE')
GIGACHAT_SCOPE: str = os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_PERS')

# YooKassa
YOOKASSA_SHOP_ID: str = os.getenv('YOOKASSA_SHOP_ID', 'YOUR_YOOKASSA_SHOP_ID_HERE')
YOOKASSA_SECRET_KEY: str = os.getenv('YOOKASSA_SECRET_KEY', 'YOUR_YOOKASSA_SECRET_KEY_HERE')

# Supabase
SUPABASE_URL: str = os.getenv('SUPABASE_URL', 'YOUR_SUPABASE_URL_HERE')
SUPABASE_KEY: str = os.getenv('SUPABASE_KEY', 'YOUR_SUPABASE_KEY_HERE')

# Настройки бота
BOT_NAME: str = "AI-юрист"
BOT_VERSION: str = "1.0.0"

# Настройки базы данных
DB_TIMEOUT: int = 30

# Настройки платежей
SUBSCRIPTION_PRICE: int = 1000  # Цена подписки в рублях
CONSULTATION_PRICE: int = 500   # Цена консультации в рублях

# Настройки файлов
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
ALLOWED_FILE_TYPES: list = ['.pdf', '.docx', '.txt']

# Проверка обязательных переменных окружения
def validate_config() -> bool:
    """
    Проверяет наличие обязательных переменных конфигурации
    """
    required_vars = [
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('GIGACHAT_CREDENTIALS', GIGACHAT_CREDENTIALS),
        ('SUPABASE_URL', SUPABASE_URL),
        ('SUPABASE_KEY', SUPABASE_KEY),
    ]
    
    missing_vars = []
    for var_name, var_value in required_vars:
        if var_value.startswith('YOUR_') or not var_value:
            missing_vars.append(var_name)
    
    if missing_vars:
        print(f"⚠️  Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        return False
    
    return True 