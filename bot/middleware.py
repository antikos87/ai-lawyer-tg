#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Middleware для проверки подписок и лимитов
"""

import logging
from functools import wraps
from typing import Callable, Any, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db_client.database import supabase_client

logger = logging.getLogger(__name__)


def subscription_required(action_type: str, friendly_name: str = None):
    """
    Декоратор для проверки подписки и лимитов перед выполнением действия
    
    Args:
        action_type: Тип действия ('consultation', 'document', 'analysis')
        friendly_name: Понятное название действия для пользователя
    """
    def decorator(handler_func: Callable):
        @wraps(handler_func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            telegram_id = update.effective_user.id
            action_friendly = friendly_name or action_type
            
            try:
                # Проверяем лимиты и логируем использование
                can_use, usage_info = await supabase_client.check_and_log_usage(
                    telegram_id=telegram_id,
                    action_type=action_type,
                    details={
                        'user_name': update.effective_user.first_name,
                        'username': update.effective_user.username
                    }
                )
                
                if can_use:
                    # Сохраняем информацию об использовании в контекст
                    context.user_data['usage_info'] = usage_info
                    
                    # Выполняем оригинальный обработчик
                    return await handler_func(update, context, *args, **kwargs)
                else:
                    # Обрабатываем разные типы ошибок
                    return await handle_usage_limit_error(update, context, usage_info, action_friendly)
                    
            except Exception as e:
                logger.error(f"Ошибка проверки подписки для {telegram_id}: {e}")
                
                # В случае ошибки показываем предупреждение
                error_message = (
                    "⚠️ **Техническая ошибка**\n\n"
                    "Не удалось проверить статус подписки.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
                
                if update.callback_query:
                    await update.callback_query.message.reply_text(error_message, parse_mode='Markdown')
                else:
                    await update.message.reply_text(error_message, parse_mode='Markdown')
                
                return None
        
        return wrapper
    return decorator


async def handle_usage_limit_error(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 usage_info: Dict[str, Any], action_name: str) -> None:
    """
    Обрабатывает ошибки лимитов использования
    """
    error_type = usage_info.get('error')
    user_name = update.effective_user.first_name or "пользователь"
    
    if error_type == 'no_subscription':
        # Нет активной подписки
        trial_used = usage_info.get('trial_used', False)
        
        if trial_used:
            message = (
                f"🔒 **Требуется подписка, {user_name}**\n\n"
                f"Для использования функции **{action_name}** необходима активная подписка.\n\n"
                "✅ Пробный период уже использован\n\n"
                "💡 **Оформите подписку для продолжения работы:**"
            )
            
            keyboard = [
                [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="subscribe_basic")],
                [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="subscribe_premium")],
                [InlineKeyboardButton("📊 Все тарифы", callback_data="subscription_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
        else:
            message = (
                f"🎯 **Попробуйте бесплатно, {user_name}!**\n\n"
                f"Для использования функции **{action_name}** нужна подписка.\n\n"
                "🆓 **Начните с бесплатного пробного периода на 1 день:**\n"
                "• 3 консультации\n"
                "• 2 документа\n"
                "• 1 анализ"
            )
            
            keyboard = [
                [InlineKeyboardButton("🆓 Попробовать БЕСПЛАТНО", callback_data="activate_trial")],
                [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="subscribe_basic")],
                [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="subscribe_premium")],
                [InlineKeyboardButton("📊 Все тарифы", callback_data="subscription_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            
    elif error_type == 'limit_exceeded':
        # Превышен лимит
        subscription_type = usage_info.get('subscription_type')
        used = usage_info.get('used', 0)
        limit = usage_info.get('limit', 0)
        
        # Названия тарифов
        type_names = {
            'trial': '🆓 Пробный',
            'basic': '💼 Базовый', 
            'premium': '🏆 Премиум',
            'corporate': '💎 Корпоративный'
        }
        
        current_plan = type_names.get(subscription_type, subscription_type)
        
        message = (
            f"📊 **Лимит исчерпан, {user_name}**\n\n"
            f"🎯 **Действие:** {action_name}\n"
            f"📋 **Текущий тариф:** {current_plan}\n"
            f"📈 **Использовано:** {used}/{limit}\n\n"
        )
        
        # Предлагаем решения в зависимости от тарифа
        if subscription_type == 'trial':
            message += "💡 **Переходите на платный тариф для продолжения:**"
            keyboard = [
                [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="subscribe_basic")],
                [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="subscribe_premium")],
                [InlineKeyboardButton("📊 Все тарифы", callback_data="subscription_menu")]
            ]
        elif subscription_type == 'basic':
            message += "⬆️ **Переходите на Премиум для безлимитных консультаций:**"
            keyboard = [
                [InlineKeyboardButton("🏆 Перейти на Премиум", callback_data="upgrade_premium")],
                [InlineKeyboardButton("💎 Корпоративный тариф", callback_data="upgrade_corporate")],
                [InlineKeyboardButton("📊 Управление подпиской", callback_data="subscription_menu")]
            ]
        else:
            message += "🔄 **Лимит восстановится в следующем месяце или перейдите на более высокий тариф.**"
            keyboard = [
                [InlineKeyboardButton("⬆️ Повысить тариф", callback_data="upgrade_menu")],
                [InlineKeyboardButton("📊 Управление подпиской", callback_data="subscription_menu")]
            ]
        
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    else:
        # Неизвестная ошибка
        message = (
            f"❌ **Ошибка доступа, {user_name}**\n\n"
            f"Не удалось выполнить действие: **{action_name}**\n\n"
            "Обратитесь в поддержку или попробуйте позже."
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Проверить подписку", callback_data="subscription_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем сообщение
    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def show_usage_warning(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           usage_info: Dict[str, Any], action_name: str) -> None:
    """
    Показывает предупреждение о приближении к лимиту
    """
    subscription_type = usage_info.get('subscription_type')
    used = usage_info.get('used', 0)
    limit = usage_info.get('limit', 0)
    
    # Проверяем, нужно ли показывать предупреждение
    if limit == -1:  # Безлимитный тариф
        return
    
    remaining = limit - used
    
    # Показываем предупреждение при остатке 20% или меньше
    if remaining <= limit * 0.2 and remaining > 0:
        warning_message = (
            f"⚠️ **Внимание: лимит заканчивается**\n\n"
            f"📊 **{action_name}:** {used}/{limit}\n"
            f"📉 **Осталось:** {remaining}\n\n"
            "💡 Рассмотрите повышение тарифа для непрерывной работы."
        )
        
        keyboard = [
            [InlineKeyboardButton("⬆️ Повысить тариф", callback_data="upgrade_menu")],
            [InlineKeyboardButton("📊 Управление подпиской", callback_data="subscription_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                warning_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                warning_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )


def add_usage_info_to_response(original_response: str, usage_info: Dict[str, Any]) -> str:
    """
    Добавляет информацию об использовании к ответу
    """
    if not usage_info.get('success'):
        return original_response
    
    subscription_type = usage_info.get('subscription_type')
    used = usage_info.get('used', 0)
    limit = usage_info.get('limit', 0)
    
    # Для безлимитных тарифов не показываем счетчик
    if limit == -1:
        return original_response
    
    # Добавляем футер с информацией об использовании
    type_names = {
        'trial': '🆓',
        'basic': '💼',
        'premium': '🏆',
        'corporate': '💎'
    }
    
    type_icon = type_names.get(subscription_type, '📊')
    
    usage_footer = f"\n\n---\n{type_icon} Использовано: {used}/{limit}"
    
    return original_response + usage_footer


# Функция для проверки статуса подписки без логирования использования
async def check_subscription_status(telegram_id: int) -> Dict[str, Any]:
    """
    Проверяет статус подписки пользователя без логирования использования
    """
    try:
        return await supabase_client.get_user_subscription_status(telegram_id)
    except Exception as e:
        logger.error(f"Ошибка проверки статуса подписки для {telegram_id}: {e}")
        return {
            'has_subscription': False,
            'subscription_type': None,
            'is_trial_used': False,
            'expires_at': None
        } 