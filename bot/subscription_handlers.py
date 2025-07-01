#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для управления подписками в боте
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from db_client.database import supabase_client
from payment_client.client import yookassa_client

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
    Главное меню подписок
    """
    telegram_id = update.effective_user.id
    
    try:
        # Получаем статус подписки пользователя
        status = await supabase_client.get_user_subscription_status(telegram_id)
        
        if status['has_subscription']:
            return await show_subscription_management(update, context, status)
        else:
            return await show_subscription_options(update, context, status)
            
    except Exception as e:
        logger.error(f"Ошибка в subscription_command для {telegram_id}: {e}")
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
    Показывает варианты подписок для пользователя без активной подписки
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
        "• 10 документов любого типа\n"
        "• 5 анализов документов\n"
        "• Базовая поддержка\n\n"
        
        "🏆 **ПРЕМИУМ - 1490₽/месяц:** ⭐ *Популярный*\n"
        "• **Безлимитные консультации** ♾️\n"
        "• 30 документов (в 3 раза больше!)\n" 
        "• 15 анализов (в 3 раза больше!)\n"
        "• Приоритетная поддержка\n"
        "• Расширенные функции\n\n"
        
        "💎 **КОРПОРАТИВНЫЙ - 3990₽/месяц:**\n"
        "• **Безлимитные консультации** ♾️\n"
        "• 100 документов (для команды)\n"
        "• 50 анализов (профессиональный уровень)\n"
        "• Персональный менеджер\n"
        "• API доступ для интеграций\n"
        "• Корпоративная поддержка 24/7\n\n"
        
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
        [InlineKeyboardButton("💼 Базовый — 790₽/мес", callback_data="subscribe_basic")],
        [InlineKeyboardButton("🏆 Премиум — 1490₽/мес ⭐", callback_data="subscribe_premium")],
        [InlineKeyboardButton("💎 Корпоративный — 3990₽/мес", callback_data="subscribe_corporate")],
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


async def show_subscription_management(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     status: Dict[str, Any]) -> int:
    """
    Показывает управление активной подпиской
    """
    try:
        # Получаем статистику использования
        usage_stats = await supabase_client.get_usage_stats(update.effective_user.id)
        
        subscription_type = status['subscription_type']
        expires_at = status['expires_at']
        
        # Названия тарифов
        type_names = {
            'trial': '🆓 Пробный',
            'basic': '💼 Базовый',
            'premium': '🏆 Премиум',
            'corporate': '💎 Корпоративный'
        }
        
        type_name = type_names.get(subscription_type, subscription_type)
        
        # Форматируем дату истечения
        expires_str = expires_at.strftime("%d.%m.%Y в %H:%M")
        
        # Формируем сообщение
        message_text = (
            f"📊 **Ваша подписка: {type_name}**\n\n"
            f"📅 **Действует до:** {expires_str}\n\n"
            "📈 **Использовано в этом месяце:**\n"
        )
        
        # Добавляем статистику использования
        consultations = usage_stats['consultations']
        documents = usage_stats['documents']
        analysis = usage_stats['analysis']
        
        def format_limit(used, limit):
            if limit == -1:
                return f"{used} (безлимит)"
            else:
                return f"{used}/{limit}"
        
        message_text += (
            f"💬 **Консультации:** {format_limit(consultations['used'], consultations['limit'])}\n"
            f"📄 **Документы:** {format_limit(documents['used'], documents['limit'])}\n"
            f"📊 **Анализы:** {format_limit(analysis['used'], analysis['limit'])}\n\n"
        )
        
        # Проверяем близость к лимитам
        warnings = []
        if consultations['limit'] != -1 and consultations['used'] >= consultations['limit'] * 0.8:
            warnings.append("💬 Консультации заканчиваются")
        if documents['limit'] != -1 and documents['used'] >= documents['limit'] * 0.8:
            warnings.append("📄 Документы заканчиваются")
        if analysis['limit'] != -1 and analysis['used'] >= analysis['limit'] * 0.8:
            warnings.append("📊 Анализы заканчиваются")
        
        if warnings:
            message_text += "⚠️ **Предупреждения:**\n" + "\n".join(f"• {w}" for w in warnings) + "\n\n"
        
        if subscription_type == 'trial':
            message_text += (
                "💡 **Пробный период заканчивается!**\n"
                "Выберите платный тариф, чтобы продолжить пользоваться всеми возможностями AI-Юрист."
            )
        else:
            message_text += "🎛️ **Управление подпиской:**"
        
        # Создаем клавиатуру в зависимости от типа подписки
        keyboard = []
        
        if subscription_type == 'trial':
            # Для пробного периода - только переход на платные тарифы
            keyboard.extend([
                [InlineKeyboardButton("⭐ Выбрать платный тариф", callback_data="trial_upgrade_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])
        else:
            # Для платных тарифов
            if subscription_type != 'corporate':  # корпоративный - максимальный тариф
                keyboard.append([InlineKeyboardButton("⬆️ Повысить тариф", callback_data="upgrade_menu")])
            
            keyboard.extend([
                [InlineKeyboardButton("🔄 Продлить подписку", callback_data="renew_subscription")],
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
        
        return SubscriptionStates.SUBSCRIPTION_MANAGEMENT.value
        
    except Exception as e:
        logger.error(f"Ошибка в show_subscription_management: {e}")
        await update.callback_query.message.reply_text(
            "❌ Ошибка загрузки информации о подписке."
        )
        return ConversationHandler.END


async def activate_trial_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Активирует пробную подписку
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "пользователь"
    
    try:
        # Проверяем, не использован ли уже пробный период
        status = await supabase_client.get_user_subscription_status(telegram_id)
        
        if status['is_trial_used']:
            await query.message.edit_text(
                "❌ **Пробный период уже использован**\n\n"
                "Вы можете оформить платную подписку для продолжения использования сервиса.",
                parse_mode='Markdown'
            )
            return await show_subscription_options(update, context, status)
        
        # Создаем пробную подписку
        subscription = await supabase_client.create_trial_subscription(telegram_id)
        
        expires_at = datetime.fromisoformat(subscription['expires_at'].replace('Z', '+00:00'))
        
        success_message = (
            f"🎉 **Поздравляем, {user_name}!**\n\n"
            "✅ **Пробный доступ активирован на 24 часа**\n\n"
            "🎯 **Что вам доступно БЕСПЛАТНО:**\n"
            "💬 **3 юридические консультации** — задайте любые правовые вопросы\n"
            "📄 **2 документа** — договоры, заявления, жалобы и др.\n"
            "📊 **1 анализ документа** — проверка соответствия закону\n\n"
            f"⏰ **Доступ истекает:** {expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
            "💡 **Рекомендуем начать с консультации!**\n"
            "Попробуйте задать любой юридический вопрос — AI-Юрист даст развернутый ответ со ссылками на законы РФ."
        )
        
        keyboard = [
            [InlineKeyboardButton("💬 Начать консультацию", callback_data="menu_consult")],
            [InlineKeyboardButton("📄 Создать документ", callback_data="menu_create")],
            [InlineKeyboardButton("📊 Анализ документа", callback_data="menu_analyze")],
            [InlineKeyboardButton("📋 Посмотреть все тарифы", callback_data="subscription_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            success_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"Активирована пробная подписка для пользователя {telegram_id}")
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка активации пробной подписки для {telegram_id}: {e}")
        
        await query.message.edit_text(
            "❌ **Ошибка активации пробного периода**\n\n"
            "Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def initiate_subscription_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Инициирует процесс оплаты подписки
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем тип подписки из callback_data
    subscription_type = query.data.replace('subscribe_', '').replace('upgrade_', '')
    
    telegram_id = update.effective_user.id
    
    try:
        # Получаем информацию о тарифе
        subscription_info = yookassa_client.get_subscription_info(subscription_type)
        
        # Создаем платеж
        payment_data = await yookassa_client.create_payment(
            telegram_id=telegram_id,
            subscription_type=subscription_type
        )
        
        # Сохраняем информацию о платеже в базу
        await supabase_client.create_payment_record(
            telegram_id=telegram_id,
            subscription_type=subscription_type,
            yookassa_payment_id=payment_data['payment_id'],
            amount_kopecks=payment_data['amount'],
            payment_url=payment_data['confirmation_url']
        )
        
        # Сохраняем данные платежа в контекст
        context.user_data['pending_payment'] = {
            'payment_id': payment_data['payment_id'],
            'subscription_type': subscription_type,
            'amount': payment_data['amount']
        }
        
        # Формируем сообщение с информацией об оплате
        type_names = {
            'basic': '💼 Базовый',
            'premium': '🏆 Премиум',
            'corporate': '💎 Корпоративный'
        }
        
        type_name = type_names.get(subscription_type, subscription_type)
        price = subscription_info['price_rubles']
        
        payment_message = (
            f"💳 **Оплата подписки: {type_name}**\n\n"
            f"💰 **Сумма:** {price:.0f} ₽\n"
            f"📅 **Период:** 1 месяц\n\n"
            "🔐 **Безопасная оплата через YooKassa**\n\n"
            "📝 **Инструкция:**\n"
            "1️⃣ Нажмите **«💳 Оплатить»** и завершите оплату\n"
            "2️⃣ После успешной оплаты нажмите **«✅ Я оплатил»**"
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить", url=payment_data['confirmation_url'])],
            [InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_payment_{payment_data['payment_id']}")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_payment")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            payment_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"Создан платеж {payment_data['payment_id']} для пользователя {telegram_id}, тариф {subscription_type}")
        return SubscriptionStates.PAYMENT_PROCESSING.value
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа для {telegram_id}: {e}")
        
        await query.message.edit_text(
            "❌ **Ошибка создания платежа**\n\n"
            "Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Проверяет статус платежа
    """
    query = update.callback_query
    await query.answer("🔄 Проверяем статус платежа...")
    
    # Извлекаем payment_id из callback_data
    payment_id = query.data.replace('check_payment_', '')
    
    try:
        # Получаем информацию о платеже
        payment_info = await yookassa_client.get_payment_info(payment_id)
        
        if payment_info['status'] == 'succeeded':
            # Платеж успешен
            metadata = payment_info['metadata']
            telegram_id = int(metadata['telegram_id'])
            subscription_type = metadata['subscription_type']
            
            # Проверяем, это продление или новая подписка
            pending_payment = context.user_data.get('pending_payment', {})
            is_renewal = pending_payment.get('is_renewal', False)
            
            if is_renewal:
                # Продлеваем существующую подписку
                subscription = await supabase_client.renew_subscription(
                    telegram_id=telegram_id,
                    payment_id=payment_id
                )
            else:
                # Создаем новую подписку
                subscription = await supabase_client.create_paid_subscription(
                    telegram_id=telegram_id,
                    subscription_type=subscription_type,
                    payment_id=payment_id
                )
            
            # Обновляем статус платежа
            await supabase_client.update_payment_status(payment_id, 'succeeded')
            
            # Сбрасываем счетчик проверок при успешном платеже
            context.user_data.pop('payment_check_count', None)
            
            # Сообщение об успехе
            type_names = {
                'basic': '💼 Базовый',
                'premium': '🏆 Премиум', 
                'corporate': '💎 Корпоративный'
            }
            
            type_name = type_names.get(subscription_type, subscription_type)
            expires_at = datetime.fromisoformat(subscription['expires_at'].replace('Z', '+00:00'))
            
            # Получаем лимиты тарифа для отображения
            limits_map = {
                'basic': {'consultations': 25, 'documents': 10, 'analysis': 5},
                'premium': {'consultations': 'безлимит', 'documents': 30, 'analysis': 15},
                'corporate': {'consultations': 'безлимит', 'documents': 100, 'analysis': 50}
            }
            
            limits = limits_map.get(subscription_type, {})
            
            if is_renewal:
                success_message = (
                    f"🎉 **Подписка успешно продлена!**\n\n"
                    f"✅ **Тариф:** {type_name}\n"
                    f"📅 **Действует до:** {expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
                    "🚀 **Продолжайте использовать все возможности AI-Юрист!**"
                )
            else:
                success_message = (
                    f"🎉 **Добро пожаловать в {type_name}!**\n\n"
                    f"✅ **Оплата прошла успешно**\n"
                    f"📅 **Подписка действует до:** {expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
                    f"🎯 **Ваши возможности:**\n"
                )
                
                if limits:
                    success_message += (
                        f"💬 **Консультации:** {limits.get('consultations', 'н/д')}\n"
                        f"📄 **Документы:** {limits.get('documents', 'н/д')}\n"
                        f"📊 **Анализы:** {limits.get('analysis', 'н/д')}\n\n"
                    )
                
                success_message += (
                    "🚀 **Готовы начать?**\n"
                    "Попробуйте любую функцию — теперь у вас полный доступ к AI-Юрист!"
                )
            
            keyboard = [
                [InlineKeyboardButton("💬 Получить консультацию", callback_data="menu_consult")],
                [InlineKeyboardButton("📄 Создать документ", callback_data="menu_create")],
                [InlineKeyboardButton("📊 Управление подпиской", callback_data="subscription_menu")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                success_message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"Успешно создана подписка {subscription_type} для пользователя {telegram_id}")
            return ConversationHandler.END
            
        elif payment_info['status'] in ['pending', 'waiting_for_capture']:
            # Платеж еще обрабатывается
            # Увеличиваем счетчик попыток проверки
            check_count = context.user_data.get('payment_check_count', 0) + 1
            context.user_data['payment_check_count'] = check_count
            
            # Формируем сообщение в зависимости от количества попыток
            if check_count <= 1:
                message = (
                    "⏳ **Обрабатываем ваш платеж...**\n\n"
                    "Платеж находится в обработке.\n"
                    "Это может занять несколько минут.\n\n"
                    "💡 Попробуйте проверить статус через минуту."
                )
            elif check_count <= 3:
                message = (
                    "⏳ **Платеж все еще обрабатывается...**\n\n"
                    f"📊 **Попытка проверки:** {check_count}\n"
                    f"📋 **Статус:** {payment_info['status']}\n\n"
                    "⏱️ Обработка может занять до 5-10 минут.\n"
                    "Пожалуйста, подождите немного дольше."
                )
            else:
                message = (
                    "⏳ **Платеж все еще в обработке**\n\n"
                    f"📊 **Проверок выполнено:** {check_count}\n"
                    f"📋 **Статус:** {payment_info['status']}\n\n"
                    "⚠️ Если платеж не прошел в течение 15 минут:\n"
                    "• Проверьте списание с карты в банке\n"
                    "• Обратитесь в поддержку @AI_support_users\n\n"
                    "🔄 Или попробуйте оформить подписку заново."
                )
            
            keyboard = [
                [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_payment_{payment_id}")],
            ]
            
            # После 3 попыток добавляем кнопку для новой попытки оплаты
            if check_count >= 3:
                keyboard.append([InlineKeyboardButton("💳 Попробовать другую оплату", callback_data="subscription_menu")])
            
            keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
            
            try:
                await query.message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception as edit_error:
                # Если не удалось отредактировать (например, сообщение не изменилось)
                # Отправляем уведомление через callback query
                if "not modified" in str(edit_error).lower():
                    await query.answer(
                        f"🔄 Проверка #{check_count}: платеж все еще обрабатывается...", 
                        show_alert=True
                    )
                else:
                    # Если другая ошибка - логируем и показываем alert
                    logger.warning(f"Ошибка редактирования сообщения: {edit_error}")
                    await query.answer("⏳ Платеж все еще обрабатывается...", show_alert=True)
            
            return SubscriptionStates.PAYMENT_PROCESSING.value
            
        else:
            # Платеж отклонен или отменен
            await query.message.edit_text(
                f"❌ **Платеж не прошел**\n\n"
                f"Статус: {payment_info['status']}\n\n"
                "Попробуйте оформить подписку заново или обратитесь в поддержку.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="subscription_menu")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}")
        
        # Пытаемся отредактировать сообщение, если не получится - показываем alert
        try:
            await query.message.edit_text(
                "❌ **Ошибка проверки платежа**\n\n"
                "Произошла техническая ошибка. Обратитесь в поддержку.",
                parse_mode='Markdown'
            )
        except Exception as edit_error:
            logger.warning(f"Не удалось отредактировать сообщение об ошибке: {edit_error}")
            await query.answer("❌ Ошибка проверки платежа. Обратитесь в поддержку.", show_alert=True)
        
        return ConversationHandler.END


async def show_upgrade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает меню повышения тарифа
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    
    try:
        # Получаем текущий статус
        status = await supabase_client.get_user_subscription_status(telegram_id)
        current_type = status['subscription_type']
        
        message_text = "⬆️ **Повышение тарифа**\n\n"
        message_text += "Выберите новый тариф:\n\n"
        
        keyboard = []
        
        # Показываем доступные варианты повышения
        if current_type == 'trial':
            keyboard.extend([
                [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="upgrade_basic")],
                [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="upgrade_premium")],
                [InlineKeyboardButton("💎 Корпоративный - 3990₽/мес", callback_data="upgrade_corporate")]
            ])
        elif current_type == 'basic':
            keyboard.extend([
                [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="upgrade_premium")],
                [InlineKeyboardButton("💎 Корпоративный - 3990₽/мес", callback_data="upgrade_corporate")]
            ])
        elif current_type == 'premium':
            keyboard.extend([
                [InlineKeyboardButton("💎 Корпоративный - 3990₽/мес", callback_data="upgrade_corporate")]
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data="subscription_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return SubscriptionStates.SUBSCRIPTION_SELECTION.value
        
    except Exception as e:
        logger.error(f"Ошибка в show_upgrade_menu: {e}")
        await query.message.edit_text("❌ Ошибка загрузки меню повышения тарифа.")
        return ConversationHandler.END


async def show_trial_upgrade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает подробное меню выбора тарифов для триал пользователя
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    user_name = update.effective_user.first_name or "пользователь"
    
    try:
        # Получаем статистику использования
        usage_stats = await supabase_client.get_usage_stats(telegram_id)
        
        message_text = (
            f"⭐ **Выберите тариф, {user_name}!**\n\n"
            "🆓 **Пробный период заканчивается** — время выбрать постоянный тариф!\n\n"
            "📊 **Сравнение тарифов:**\n\n"
            
            "💼 **БАЗОВЫЙ — 790₽/месяц**\n"
            "• 25 консультаций (сейчас у вас: 3)\n"
            "• 10 документов (сейчас у вас: 2)\n"
            "• 5 анализов (сейчас у вас: 1)\n"
            "• Базовая поддержка\n\n"
            
            "🏆 **ПРЕМИУМ — 1490₽/месяц** ⭐ *Популярный*\n"
            "• **Безлимитные консультации** ♾️\n"
            "• 30 документов (в 15 раз больше!)\n"
            "• 15 анализов (в 15 раз больше!)\n"
            "• Приоритетная поддержка\n"
            "• Расширенные функции\n\n"
            
            "💎 **КОРПОРАТИВНЫЙ — 3990₽/месяц**\n"
            "• **Безлимитные консультации** ♾️\n"
            "• 100 документов (в 50 раз больше!)\n"
            "• 50 анализов (в 50 раз больше!)\n"
            "• Персональный менеджер\n"
            "• API доступ для интеграций\n"
            "• Корпоративная поддержка 24/7\n\n"
            
            "💡 **Рекомендация:** Для личного использования оптимален тариф **Премиум** — "
            "безлимитные консультации + щедрые лимиты на документы!"
        )
        
        keyboard = [
            [InlineKeyboardButton("💼 Выбрать Базовый — 790₽", callback_data="subscribe_basic")],
            [InlineKeyboardButton("🏆 Выбрать Премиум — 1490₽", callback_data="subscribe_premium")],
            [InlineKeyboardButton("💎 Выбрать Корпоративный — 3990₽", callback_data="subscribe_corporate")],
            [InlineKeyboardButton("🔙 Назад к статистике", callback_data="subscription_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return SubscriptionStates.SUBSCRIPTION_SELECTION.value
        
    except Exception as e:
        logger.error(f"Ошибка в show_trial_upgrade_menu: {e}")
        await query.message.edit_text("❌ Ошибка загрузки тарифов.")
        return ConversationHandler.END


async def renew_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Продлевает текущую подписку на тот же тариф
    """
    query = update.callback_query
    await query.answer()
    
    telegram_id = update.effective_user.id
    
    try:
        # Получаем текущий статус подписки
        status = await supabase_client.get_user_subscription_status(telegram_id)
        
        if not status['has_subscription']:
            await query.message.edit_text(
                "❌ **Нет активной подписки**\n\n"
                "У вас нет активной подписки для продления.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
            
        subscription_type = status['subscription_type']
        
        # Пробный период нельзя продлить
        if subscription_type == 'trial':
            await query.message.edit_text(
                "❌ **Пробный период нельзя продлить**\n\n"
                "Пожалуйста, выберите один из платных тарифов:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💼 Базовый - 790₽/мес", callback_data="subscribe_basic")],
                    [InlineKeyboardButton("🏆 Премиум - 1490₽/мес", callback_data="subscribe_premium")],
                    [InlineKeyboardButton("💎 Корпоративный - 3990₽/мес", callback_data="subscribe_corporate")],
                    [InlineKeyboardButton("❌ Отменить", callback_data="subscription_menu")]
                ]),
                parse_mode='Markdown'
            )
            return SubscriptionStates.SUBSCRIPTION_SELECTION.value
        
        # Получаем информацию о тарифе
        subscription_info = yookassa_client.get_subscription_info(subscription_type)
        
        # Создаем платеж для продления
        payment_data = await yookassa_client.create_payment(
            telegram_id=telegram_id,
            subscription_type=subscription_type
        )
        
        # Сохраняем информацию о платеже в базу
        await supabase_client.create_payment_record(
            telegram_id=telegram_id,
            subscription_type=subscription_type,
            yookassa_payment_id=payment_data['payment_id'],
            amount_kopecks=payment_data['amount'],
            payment_url=payment_data['confirmation_url']
        )
        
        # Сохраняем данные платежа в контекст
        context.user_data['pending_payment'] = {
            'payment_id': payment_data['payment_id'],
            'subscription_type': subscription_type,
            'amount': payment_data['amount'],
            'is_renewal': True  # Флаг продления
        }
        
        # Формируем сообщение о продлении
        type_names = {
            'basic': '💼 Базовый',
            'premium': '🏆 Премиум',
            'corporate': '💎 Корпоративный'
        }
        
        type_name = type_names.get(subscription_type, subscription_type)
        price = subscription_info['price_rubles']
        expires_at = status['expires_at']
        
        # Рассчитываем новую дату окончания
        new_expires_at = expires_at + timedelta(days=30)
        
        renewal_message = (
            f"🔄 **Продление подписки: {type_name}**\n\n"
            f"💰 **Сумма:** {price:.0f} ₽\n"
            f"📅 **Период:** 1 месяц\n\n"
            f"⏰ **Текущая подписка действует до:** {expires_at.strftime('%d.%m.%Y в %H:%M')}\n"
            f"🆕 **После продления будет действовать до:** {new_expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
            "🔐 **Безопасная оплата через YooKassa**\n\n"
            "📝 **Инструкция:**\n"
            "1️⃣ Нажмите **«💳 Оплатить продление»** и завершите оплату\n"
            "2️⃣ После успешной оплаты нажмите **«✅ Я оплатил»**"
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить продление", url=payment_data['confirmation_url'])],
            [InlineKeyboardButton("✅ Я оплатил", callback_data=f"check_payment_{payment_data['payment_id']}")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_payment")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            renewal_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"Инициировано продление подписки {subscription_type} для пользователя {telegram_id}")
        return SubscriptionStates.PAYMENT_PROCESSING.value
        
    except Exception as e:
        logger.error(f"Ошибка продления подписки для {telegram_id}: {e}")
        
        await query.message.edit_text(
            "❌ **Ошибка создания платежа**\n\n"
            "Произошла техническая ошибка. Попробуйте позже или обратитесь в поддержку.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отменяет текущий платеж и возвращает в меню подписок
    """
    query = update.callback_query
    await query.answer()
    
    # Очищаем данные о платеже
    context.user_data.pop('pending_payment', None)
    context.user_data.pop('payment_check_count', None)
    
    await query.message.edit_text(
        "❌ **Платеж отменен**\n\n"
        "Вы можете оформить подписку в любое время.\n\n"
        "💡 Выберите действие:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Управление подпиской", callback_data="subscription_menu")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]),
        parse_mode='Markdown'
    )
    
    logger.info(f"Платеж отменен пользователем {update.effective_user.id}")
    return ConversationHandler.END


# Главные обработчики callback
subscription_handlers = {
    'subscription_menu': subscription_command,
    'activate_trial': activate_trial_subscription,
    'subscribe_basic': initiate_subscription_payment,
    'subscribe_premium': initiate_subscription_payment,
    'subscribe_corporate': initiate_subscription_payment,
    'upgrade_basic': initiate_subscription_payment,
    'upgrade_premium': initiate_subscription_payment,
    'upgrade_corporate': initiate_subscription_payment,
    'upgrade_menu': show_upgrade_menu,
    'renew_subscription': renew_subscription,
    'cancel_payment': cancel_payment,
    'trial_upgrade_menu': show_trial_upgrade_menu,
} 