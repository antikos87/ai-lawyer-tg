#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Упрощенные обработчики подписок (без Supabase) для тестирования
"""

import logging
from enum import Enum
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


class SubscriptionStates(Enum):
    """Состояния диалога подписки"""
    MAIN_MENU = 0
    SUBSCRIPTION_SELECTION = 1
    TRIAL_ACTIVATION = 2
    PAYMENT_PROCESSING = 3
    SUBSCRIPTION_MANAGEMENT = 4


async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /subscription - главное меню подписок
    """
    try:
        # Эмулируем пользователя без подписки
        fake_status = {
            'has_subscription': False,
            'subscription_type': None,
            'is_trial_used': False,
            'expires_at': None
        }
        
        return await show_subscription_options(update, context, fake_status)
            
    except Exception as e:
        logger.error(f"Ошибка в subscription_command: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "❌ Произошла ошибка при загрузке информации о подписке.\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при загрузке информации о подписке.\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
        return ConversationHandler.END


async def show_subscription_options(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  status: Dict[str, Any]) -> int:
    """
    Показывает варианты подписок
    """
    user_name = update.effective_user.first_name or "пользователь"
    
    # Формируем сообщение
    if status['is_trial_used']:
        header = f"💎 **Выберите подписку, {user_name}!**\n\n"
        trial_info = "✅ *Пробный период уже использован*\n\n"
    else:
        header = f"🎯 **Добро пожаловать, {user_name}!**\n\n"
        trial_info = (
            "🆓 **БЕСПЛАТНЫЙ ПРОБНЫЙ ПЕРИОД - 1 ДЕНЬ:**\n"
            "• 3 консультации\n"
            "• 2 документа\n" 
            "• 1 анализ\n\n"
        )
    
    subscription_info = (
        "💼 **БАЗОВЫЙ - 790₽/месяц:**\n"
        "• 25 консультаций\n"
        "• 10 документов\n"
        "• 5 анализов\n\n"
        
        "🏆 **ПРЕМИУМ - 1490₽/месяц:**\n"
        "• Безлимитные консультации\n"
        "• 30 документов\n" 
        "• 15 анализов\n"
        "• Приоритетная поддержка\n\n"
        
        "💎 **КОРПОРАТИВНЫЙ - 3990₽/месяц:**\n"
        "• Все функции Премиум\n"
        "• 100 документов\n"
        "• 50 анализов\n"
        "• API доступ\n\n"
        
        "📋 **Выберите подходящий тариф:**"
    )
    
    message_text = header + trial_info + subscription_info
    
    # Создаем клавиатуру
    keyboard = []
    
    # Кнопка пробного периода (если не использован)
    if not status['is_trial_used']:
        keyboard.append([InlineKeyboardButton("🆓 Попробовать БЕСПЛАТНО (1 день)", callback_data="activate_trial")])
        keyboard.append([])  # Разделитель
    
    # Кнопки платных тарифов
    keyboard.extend([
        [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="subscribe_basic")],
        [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="subscribe_premium")],
        [InlineKeyboardButton("💎 Корпоративный - 3990₽/мес", callback_data="subscribe_corporate")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return SubscriptionStates.SUBSCRIPTION_SELECTION.value


async def activate_trial_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Активация пробной подписки (эмуляция)
    """
    query = update.callback_query
    await query.answer()
    
    message_text = (
        "🎉 **Поздравляем!**\n\n"
        "✅ Пробная подписка активирована!\n"
        "📅 Действует до: 02.07.2025\n\n"
        "🎯 **Доступно:**\n"
        "• 3 консультации\n"
        "• 2 документа\n"
        "• 1 анализ\n\n"
        "💡 Используйте все возможности AI-юриста!"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Начать консультацию", callback_data="start_consult")],
        [InlineKeyboardButton("📄 Создать документ", callback_data="start_create")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END


async def initiate_subscription_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Инициация платежа (эмуляция)
    """
    query = update.callback_query
    await query.answer()
    
    subscription_type = query.data.replace("subscribe_", "")
    
    prices = {
        'basic': '790₽',
        'premium': '1490₽',
        'corporate': '3990₽'
    }
    
    names = {
        'basic': 'Базовый',
        'premium': 'Премиум', 
        'corporate': 'Корпоративный'
    }
    
    price = prices.get(subscription_type)
    name = names.get(subscription_type)
    
    message_text = (
        f"💳 **Оплата тарифа {name}**\n\n"
        f"💰 Сумма: {price}/месяц\n\n"
        "🔗 **Ссылка для оплаты:**\n"
        "https://yookassa.ru/checkout/payments/test-demo\n\n"
        "⚠️ *Это демо-ссылка для тестирования*\n\n"
        "После оплаты подписка активируется автоматически."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"payment_success_{subscription_type}")],
        [InlineKeyboardButton("❌ Отменить", callback_data="subscription_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return SubscriptionStates.PAYMENT_PROCESSING.value


async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Проверка статуса платежа (эмуляция успешной оплаты)
    """
    query = update.callback_query
    await query.answer()
    
    subscription_type = query.data.replace("payment_success_", "")
    
    names = {
        'basic': 'Базовый',
        'premium': 'Премиум',
        'corporate': 'Корпоративный'
    }
    
    name = names.get(subscription_type, subscription_type)
    
    message_text = (
        "🎉 **Платеж успешно обработан!**\n\n"
        f"✅ Подписка **{name}** активирована\n"
        "📅 Действует до: 01.08.2025\n\n"
        "🚀 **Теперь вам доступны:**\n"
        "• Все функции выбранного тарифа\n"
        "• Приоритетная поддержка\n"
        "• Регулярные обновления\n\n"
        "Добро пожаловать в AI-юрист!"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Начать работу", callback_data="start_consult")],
        [InlineKeyboardButton("📊 Мои подписки", callback_data="subscription_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END


async def cancel_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик отмены подписки
    """
    return ConversationHandler.END


# Маппинг callback_data на функции
subscription_handlers = {
    "activate_trial": activate_trial_subscription,
    "subscribe_basic": initiate_subscription_payment,
    "subscribe_premium": initiate_subscription_payment,
    "subscribe_corporate": initiate_subscription_payment,
    "payment_success_basic": check_payment_status,
    "payment_success_premium": check_payment_status,
    "payment_success_corporate": check_payment_status,
} 