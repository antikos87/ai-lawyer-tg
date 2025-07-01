#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-юрист Telegram Bot
Основной файл для запуска бота
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from typing import Dict, Any, List

from config import TELEGRAM_TOKEN
from bot.handlers import (
    consult_command, category_selected, process_question, 
    back_to_categories, cancel_consultation, ConsultationStates,
    main_menu_callback, continue_consultation, process_dialog_message,
    continue_dialog, end_consultation
)

from bot.document_handlers import (
    DocumentStates, create_command, document_type_selected, document_subtype_selected,
    start_data_collection, process_answer, handle_document_review,
    start_document_editing, start_document_supplement, process_document_changes,
    regenerate_document, finalize_document, handle_document_rating,
    back_to_types, back_to_subtypes, cancel_document_creation,
    cancel_custom_answer, cancel_edit, cancel_supplement
)

from bot.analysis_handlers import (
    AnalysisStates, analyze_command, handle_document_upload, handle_analysis_type_selection,
    handle_additional_actions, cancel_analysis
)

from bot.subscription_handlers import (
    SubscriptionStates, subscription_command, activate_trial_subscription,
    initiate_subscription_payment, check_payment_status,
    subscription_handlers, show_upgrade_menu, renew_subscription, cancel_payment,
    show_trial_upgrade_menu
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def determine_user_type(status: Dict[str, Any]) -> str:
    """
    Определяет тип пользователя на основе статуса подписки
    """
    if not status['has_subscription'] and not status['is_trial_used']:
        return "new_user"
    elif not status['has_subscription'] and status['is_trial_used']:
        return "expired_user"
    elif status['has_subscription'] and status['subscription_type'] == 'trial':
        return "trial_user"
    elif status['has_subscription']:
        return "active_user"
    else:
        return "new_user"


def format_usage_stats(stats: Dict[str, Any]) -> str:
    """
    Форматирует статистику использования для отображения
    """
    if not stats.get('has_subscription'):
        return ""
    
    def format_limit(used: int, limit: int) -> str:
        if limit == -1:
            return f"{used} (безлимит)"
        else:
            return f"{used}/{limit}"
    
    consultations = stats['consultations']
    documents = stats['documents']
    analysis = stats['analysis']
    
    return (
        f"💬 Консультации: {format_limit(consultations['used'], consultations['limit'])}\n"
        f"📄 Документы: {format_limit(documents['used'], documents['limit'])}\n"
        f"📊 Анализы: {format_limit(analysis['used'], analysis['limit'])}"
    )


def get_usage_warnings(stats: Dict[str, Any]) -> List[str]:
    """
    Определяет предупреждения о приближении к лимитам
    """
    warnings = []
    
    if not stats.get('has_subscription'):
        return warnings
    
    consultations = stats['consultations']
    documents = stats['documents']
    analysis = stats['analysis']
    
    # Проверяем лимиты (предупреждение при 80% использования)
    if consultations['limit'] != -1 and consultations['used'] >= consultations['limit'] * 0.8:
        warnings.append("💬 Консультации заканчиваются")
    if documents['limit'] != -1 and documents['used'] >= documents['limit'] * 0.8:
        warnings.append("📄 Документы заканчиваются")
    if analysis['limit'] != -1 and analysis['used'] >= analysis['limit'] * 0.8:
        warnings.append("📊 Анализы заканчиваются")
    
    return warnings


async def get_personalized_main_menu(telegram_id: int, user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Возвращает персонализированное главное меню в зависимости от статуса пользователя
    """
    try:
        from db_client.database import supabase_client
        
        # Получаем статус подписки
        status = await supabase_client.get_user_subscription_status(telegram_id)
        user_type = determine_user_type(status)
        
        if user_type == "new_user":
            return get_new_user_menu(user_name)
        elif user_type == "trial_user":
            stats = await supabase_client.get_usage_stats(telegram_id)
            return get_trial_user_menu(user_name, status, stats)
        elif user_type == "active_user":
            stats = await supabase_client.get_usage_stats(telegram_id)
            return get_active_user_menu(user_name, status, stats)
        elif user_type == "expired_user":
            return get_expired_user_menu(user_name, status)
        else:
            return get_new_user_menu(user_name)
            
    except Exception as e:
        logger.error(f"Ошибка персонализации меню для {telegram_id}: {e}")
        # Возвращаем дефолтное меню при ошибке
        return get_default_menu(user_name)


def get_new_user_menu(user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Меню для нового пользователя (без подписки, пробный период не использован)
    """
    message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 Добро пожаловать, {user_name}!\n\n"
        
        "🎯 **Попробуйте БЕСПЛАТНО:**\n"
        "• 3 юридические консультации\n"
        "• 2 документа любого типа\n"
        "• 1 анализ документа\n"
        "• Доступ на 24 часа\n\n"
        
        "💡 **Что умеет AI-Юрист:**\n"
        "✅ Консультации по 6 отраслям права\n"
        "✅ Создание 40+ типов документов\n"
        "✅ Анализ и проверка документов\n"
        "✅ Экспорт в Word, соответствие законам РФ\n\n"
        
        "🚀 **Начните прямо сейчас!**"
    )
    
    keyboard = [
        [InlineKeyboardButton("🆓 Активировать пробный доступ", callback_data="activate_trial")],
        [InlineKeyboardButton("📋 Посмотреть все тарифы", callback_data="subscription_menu")],
        [InlineKeyboardButton("ℹ️ Подробнее о сервисе", callback_data="menu_help")]
    ]
    
    return message, InlineKeyboardMarkup(keyboard)


def get_trial_user_menu(user_name: str, status: Dict[str, Any], stats: Dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Меню для пользователя с активным пробным периодом
    """
    expires_at = status['expires_at']
    usage_text = format_usage_stats(stats)
    warnings = get_usage_warnings(stats)
    
    # Рассчитываем время до окончания
    time_left = expires_at - expires_at.replace(hour=expires_at.hour)  # Временная заглушка
    
    message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 Привет, {user_name}!\n\n"
        
        f"🆓 **Пробный доступ активен**\n"
        f"📅 Истекает: {expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
        
        f"📊 **Использовано:**\n{usage_text}\n\n"
    )
    
    if warnings:
        message += "⚠️ **Лимиты заканчиваются:**\n" + "\n".join(f"• {w}" for w in warnings) + "\n\n"
        message += "💡 **Совет:** Оформите подписку сейчас, чтобы не потерять доступ!\n\n"
    
    message += "💼 **Что попробуем сегодня?**"
    
    keyboard = [
        [InlineKeyboardButton("💬 Юридическая консультация", callback_data="menu_consult")],
        [InlineKeyboardButton("📄 Создание документов", callback_data="menu_create")],
        [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
        [InlineKeyboardButton("⭐ Выбрать тариф", callback_data="subscription_menu")],
        [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
    ]
    
    return message, InlineKeyboardMarkup(keyboard)


def get_active_user_menu(user_name: str, status: Dict[str, Any], stats: Dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Меню для пользователя с активной платной подпиской
    """
    subscription_type = status['subscription_type']
    expires_at = status['expires_at']
    usage_text = format_usage_stats(stats)
    warnings = get_usage_warnings(stats)
    
    # Названия тарифов
    type_names = {
        'basic': '💼 Базовый',
        'premium': '🏆 Премиум',
        'corporate': '💎 Корпоративный'
    }
    
    type_name = type_names.get(subscription_type, subscription_type)
    
    message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 Добро пожаловать, {user_name}!\n\n"
        
        f"💎 **Ваша подписка: {type_name}**\n"
        f"📅 Действует до: {expires_at.strftime('%d.%m.%Y в %H:%M')}\n\n"
        
        f"📊 **Использовано в этом месяце:**\n{usage_text}\n\n"
    )
    
    if warnings:
        message += "⚠️ **Предупреждения:**\n" + "\n".join(f"• {w}" for w in warnings) + "\n\n"
        message += "💡 **Совет:** Рассмотрите повышение тарифа для большего комфорта!\n\n"
    
    # Определяем время до окончания подписки для мотивационного сообщения
    from datetime import datetime
    days_left = (expires_at - datetime.now(expires_at.tzinfo)).days
    
    if days_left <= 3:
        message += f"⏰ **Подписка истекает через {days_left} дн.** Не забудьте продлить!\n\n"
    
    message += "💼 **Выберите нужную услугу:**"
    
    keyboard = [
        [InlineKeyboardButton("💬 Юридическая консультация", callback_data="menu_consult")],
        [InlineKeyboardButton("📄 Создание документов", callback_data="menu_create")],
        [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
        [InlineKeyboardButton("💎 Управление подпиской", callback_data="subscription_menu")],
        [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
    ]
    
    return message, InlineKeyboardMarkup(keyboard)


def get_expired_user_menu(user_name: str, status: Dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
    """
    Меню для пользователя с истекшей подпиской
    """
    message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 С возвращением, {user_name}!\n\n"
        
        "⚠️ **Ваша подписка истекла**\n\n"
        
        "💡 **Что можно сделать:**\n"
        "🔄 **Продлить доступ** — вернуть все функции одним кликом\n"
        "💬 **Получить консультацию** — оплатить разово\n"
        "📄 **Создать документ** — без подписки\n\n"
        
        "💰 **Выгодно с подпиской:**\n"
        "📊 Экономия до 70% при месячной подписке\n"
        "🎯 Лимиты на все функции в одном тарифе\n"
        "⚡ Мгновенный доступ без повторных оплат"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Оформить подписку", callback_data="subscription_menu")],
        [InlineKeyboardButton("💬 Разовая консультация", callback_data="single_consult")],
        [InlineKeyboardButton("📄 Разовый документ", callback_data="single_document")],
        [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
    ]
    
    return message, InlineKeyboardMarkup(keyboard)


def get_default_menu(user_name: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    Дефолтное меню на случай ошибок
    """
    message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 Привет, {user_name}!\n\n"
        
        "🎯 **Проверенный сервис:**\n"
        "• 6 отраслей права\n"
        "• 40+ типов документов\n"
        "• Экспорт в Word\n\n"
        
        "💼 **Выберите нужную услугу:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Юридическая консультация", callback_data="menu_consult")],
        [InlineKeyboardButton("📄 Создание документов", callback_data="menu_create")],
        [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
        [InlineKeyboardButton("💎 Подписка", callback_data="subscription_menu")],
        [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
    ]
    
    return message, InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    Отправляет главное меню с inline-кнопками
    """
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    # Проверяем параметры команды /start
    args = context.args
    if args and args[0] == "payment_success":
        # Пользователь вернулся после успешной оплаты
        payment_success_message = (
            f"🎉 **Добро пожаловать обратно, {user_name}!**\n\n"
            "✅ **Оплата прошла успешно!**\n\n"
            "Ваша подписка уже активирована. Проверьте статус в разделе «Подписка».\n\n"
            "🚀 **Начните использовать все возможности AI-Юрист!**"
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Проверить подписку", callback_data="subscription_menu")],
            [InlineKeyboardButton("💬 Получить консультацию", callback_data="menu_consult")],
            [InlineKeyboardButton("📄 Создать документ", callback_data="menu_create")],
            [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            payment_success_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Получаем персонализированное меню на основе статуса пользователя
    if user:
        telegram_id = user.id
        message_text, keyboard = await get_personalized_main_menu(telegram_id, user_name)
    else:
        message_text, keyboard = get_default_menu(user_name)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /help - подробная справка
    """
    help_text = (
        "📚 **Подробная справка по AI-юристу**\n\n"
        
        "🎯 **Основные возможности:**\n\n"
        
        "💬 **Юридическая консультация**\n"
        "Получите ответы на правовые вопросы от AI-юриста\n"
        "6 отраслей права: гражданское, уголовное, семейное, трудовое, жилищное, административное\n\n"
        
        "📄 **Создание документов**\n" 
        "Генерация 40+ типов юридических документов\n"
        "Автоматическое заполнение и экспорт в Word\n\n"
        
        "📊 **Анализ документов**\n"
        "Проверка соответствия закону, поиск ошибок, оценка рисков\n\n"
        
        "🎛️ **Навигация:**\n"
        "• Используйте кнопки в меню для выбора услуг\n"
        "• Кнопка 'Главное меню' вернет на главную\n"
        "• Кнопка 'Отмена' прервет текущее действие\n\n"
        
        "🔒 **Безопасность:**\n"
        "• Данные не сохраняются на серверах\n"
        "• Автоматическое удаление файлов\n"
        "• Шифрованная передача\n\n"
        
        "📞 **Поддержка:** @AI_support_users"
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def show_detailed_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Показывает подробную интерактивную справку с разделами
    """
    query = update.callback_query
    await query.answer()
    
    user_name = update.effective_user.first_name if update.effective_user.first_name else "пользователь"
    
    help_text = (
        f"📚 **Подробная справка AI-Юрист**\n\n"
        f"👋 Привет, {user_name}! Выберите интересующий раздел:\n\n"
        
        "🎯 **Что вас интересует?**"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 Как начать работу", callback_data="help_getting_started"),
            InlineKeyboardButton("💬 Консультации", callback_data="help_consultations")
        ],
        [
            InlineKeyboardButton("📄 Создание документов", callback_data="help_documents"),
            InlineKeyboardButton("📊 Анализ документов", callback_data="help_analysis")
        ],
        [
            InlineKeyboardButton("💰 Тарифы и оплата", callback_data="help_pricing"),
            InlineKeyboardButton("🔧 Технические вопросы", callback_data="help_technical")
        ],
        [
            InlineKeyboardButton("🛡️ Безопасность", callback_data="help_security"),
            InlineKeyboardButton("⚠️ Решение проблем", callback_data="help_troubleshooting")
        ],
        [
            InlineKeyboardButton("🤖 О технологии", callback_data="help_technology"),
            InlineKeyboardButton("📞 Контакты", callback_data="help_contacts")
        ],
        [
            InlineKeyboardButton("⬅️ Назад к справке", callback_data="menu_help")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_help_section(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик разделов подробной справки
    """
    query = update.callback_query
    await query.answer()
    
    section = query.data.replace("help_", "")
    
    # Словарь с контентом для каждого раздела
    help_sections = {
        "getting_started": {
            "title": "🚀 **Как начать работу с AI-Юрист**",
            "content": (
                "**Простой старт в 3 шага:**\n\n"
                
                "**1️⃣ Активируйте пробный период**\n"
                "• Нажмите кнопку «💎 Управление подпиской»\n"
                "• Выберите «🆓 Активировать пробный период»\n"
                "• Получите 24 часа бесплатно без привязки карты\n\n"
                
                "**2️⃣ Выберите нужную услугу**\n"
                "• **💬 Консультация** — задайте правовой вопрос\n"
                "• **📄 Документы** — создайте договор или заявление\n"
                "• **📊 Анализ** — проверьте свой документ\n\n"
                
                "**3️⃣ Получите результат**\n"
                "• Через 30-60 секунд получите профессиональный ответ\n"
                "• Документы можно экспортировать в Word\n"
                "• Задавайте уточняющие вопросы в диалоге\n\n"
                
                "💡 **Совет:** Начните с консультации, чтобы понять возможности системы!"
            )
        },
        
        "consultations": {
            "title": "💬 **Юридические консультации**",
            "content": (
                "**Как получить качественную консультацию:**\n\n"
                
                "**📋 Выберите категорию права:**\n"
                "• 🏠 **Гражданское** — договоры, собственность, наследство\n"
                "• ⚖️ **Уголовное** — преступления, процедуры, защита\n"
                "• 👨‍👩‍👧‍👦 **Семейное** — брак, развод, алименты\n"
                "• 💼 **Трудовое** — увольнения, зарплата, споры\n"
                "• 🏘️ **Жилищное** — аренда, ЖКХ, недвижимость\n"
                "• 📋 **Административное** — штрафы, госуслуги\n\n"
                
                "**✍️ Опишите ситуацию подробно:**\n"
                "• Суть проблемы и что произошло\n"
                "• Какие документы у вас есть\n"
                "• Что уже предпринимали\n"
                "• Какой результат хотите получить\n"
                "• Регион (законы могут отличаться)\n\n"
                
                "**💬 Продолжайте диалог:**\n"
                "• Задавайте уточняющие вопросы\n"
                "• Просите разъяснить термины\n"
                "• Уточняйте практические шаги\n\n"
                
                "⚠️ **Важно:** AI-консультация не заменяет живого юриста при сложных спорах"
            )
        },
        
        "documents": {
            "title": "📄 **Создание документов**",
            "content": (
                "**40+ типов юридических документов:**\n\n"
                
                "**📋 Договоры:**\n"
                "• Аренды жилья и коммерческой недвижимости\n"
                "• Купли-продажи (авто, недвижимость, товары)\n"
                "• Оказания услуг и подряда\n"
                "• Займа и кредитные соглашения\n\n"
                
                "**⚖️ Судебные документы:**\n"
                "• Исковые заявления (взыскание долгов, защита прав)\n"
                "• Возражения на иски\n"
                "• Ходатайства и жалобы\n\n"
                
                "**📝 Претензии и заявления:**\n"
                "• Досудебные претензии\n"
                "• Заявления в госорганы\n"
                "• Жалобы на некачественные услуги\n\n"
                
                "**🎯 Процесс создания:**\n"
                "1. Выберите тип документа\n"
                "2. Ответьте на простые вопросы\n"
                "3. Получите готовый документ\n"
                "4. Экспортируйте в Word для редактирования\n\n"
                
                "💡 **Совет:** Внимательно проверьте все данные перед использованием"
            )
        },
        
        "analysis": {
            "title": "📊 **Анализ документов**",
            "content": (
                "**Профессиональный анализ ваших документов:**\n\n"
                
                "**📄 Поддерживаемые форматы:**\n"
                "• **Документы:** PDF, DOC, DOCX (до 10 МБ)\n"
                "• **Изображения:** JPG, PNG (сканы документов)\n"
                "• **Текст:** можно вставить напрямую\n\n"
                
                "**🔍 Типы анализа:**\n"
                "• **📋 Краткое описание** — суть и назначение документа\n"
                "• **⚖️ Проверка закону** — соответствие российскому праву\n"
                "• **🔍 Поиск ошибок** — юридические и технические недочеты\n"
                "• **⚠️ Оценка рисков** — потенциальные правовые проблемы\n"
                "• **💡 Рекомендации** — как улучшить документ\n"
                "• **📧 Анализ переписки** — деловая коммуникация\n\n"
                
                "**⏱️ Время обработки:**\n"
                "• Простые документы: 30-60 секунд\n"
                "• Сложные документы: до 2 минут\n"
                "• Большие файлы: до 3 минут\n\n"
                
                "💡 **Совет:** Для лучшего анализа используйте четкие сканы или оригинальные файлы"
            )
        },
        
        "pricing": {
            "title": "💰 **Тарифы и оплата**",
            "content": (
                "**Прозрачная тарифная система:**\n\n"
                
                "**🆓 ПРОБНЫЙ ПЕРИОД — 24 часа бесплатно**\n"
                "• 3 консультации\n"
                "• 2 документа\n"
                "• 1 анализ\n"
                "• Без привязки карты\n\n"
                
                "**💼 БАЗОВЫЙ — 790₽/месяц**\n"
                "• 25 консультаций\n"
                "• 10 документов\n"
                "• 5 анализов\n"
                "• Базовая поддержка\n\n"
                
                "**🏆 ПРЕМИУМ — 1490₽/месяц** ⭐\n"
                "• **Безлимитные консультации**\n"
                "• 30 документов\n"
                "• 15 анализов\n"
                "• Приоритетная поддержка\n\n"
                
                "**💎 КОРПОРАТИВНЫЙ — 3990₽/месяц**\n"
                "• **Безлимитные консультации**\n"
                "• 100 документов\n"
                "• 50 анализов\n"
                "• Персональный менеджер\n\n"
                
                "**💳 Способы оплаты:**\n"
                "• Банковские карты (Visa, MasterCard, МИР)\n"
                "• СБП (Система быстрых платежей)\n"
                "• Автопродление отключено по умолчанию"
                
                    )
        },
        
        "technical": {
            "title": "🔧 **Технические вопросы**",
            "content": (
                "**Решение частых технических проблем:**\n\n"
                
                "**⏱️ Долго генерируется ответ:**\n"
                "• Нормальное время: 15-90 секунд\n"
                "• Если дольше 3 минут — обновите чат\n"
                "• Попробуйте переформулировать вопрос\n\n"
                
                "**🤖 Бот не отвечает:**\n"
                "1. Подождите 2-3 минуты\n"
                "2. Нажмите «Главное меню»\n"
                "3. Перезапустите бота командой /start\n"
                "4. Обратитесь в поддержку\n\n"
                
                "**📄 Не загружается документ:**\n"
                "• Проверьте размер файла (до 10 МБ)\n"
                "• Поддерживаемые форматы: PDF, DOC, DOCX, JPG, PNG\n"
                "• Убедитесь, что файл не поврежден\n"
                "• Попробуйте сжать файл\n\n"
                
                "**💳 Проблемы с оплатой:**\n"
                "• Проверьте баланс карты\n"
                "• Убедитесь, что карта поддерживает онлайн-платежи\n"
                "• Попробуйте другую карту\n"
                "• Обратитесь в поддержку с ID платежа\n\n"
                
                "**📱 Проблемы в мобильном приложении:**\n"
                "• Используйте официальный Telegram\n"
                "• Обновите приложение до последней версии\n"
                "• Очистите кеш Telegram\n"
                "• Перезагрузите устройство"
            )
        },
        
        "security": {
            "title": "🛡️ **Безопасность и конфиденциальность**",
            "content": (
                "**Максимальная защита ваших данных:**\n\n"
                
                "**🔒 Конфиденциальность:**\n"
                "• Документы НЕ сохраняются на серверах\n"
                "• Автоматическое удаление после обработки\n"
                "• Личные данные НЕ передаются третьим лицам\n"
                "• История консультаций хранится только в сессии\n\n"
                
                "**🔐 Техническая защита:**\n"
                "• Шифрованная передача данных (TLS 1.3)\n"
                "• Защищенные серверы в России\n"
                "• Регулярные аудиты безопасности\n"
                "• Соответствие 152-ФЗ о персональных данных\n\n"
                
                "**🤖 Обработка AI:**\n"
                "• Используется российская модель GigaChat\n"
                "• Данные обрабатываются на территории РФ\n"
                "• Соответствие требованиям регуляторов\n"
                "• Нет передачи данных зарубежным сервисам\n\n"
                
                "**⚠️ Рекомендации:**\n"
                "• Не указывайте номера паспортов в консультациях\n"
                "• Можете заменять реальные имена на «А» и «Б»\n"
                "• Для особо важных дел — консультация с живым юристом\n"
                "• При работе с коммерческой тайной — используйте общие формулировки\n\n"
                
                "**🔍 Аудит и контроль:**\n"
                "• Регулярные проверки безопасности\n"
                "• Мониторинг доступа к данным\n"
                "• Журналирование всех операций\n"
                "• Соответствие стандартам информационной безопасности"
            )
        },
        
        "troubleshooting": {
            "title": "⚠️ **Решение проблем**",
            "content": (
                "**Что делать, если что-то пошло не так:**\n\n"
                
                "**💳 Списались деньги, но подписка не активна:**\n"
                "1. Проверьте раздел «Подписка» в боте\n"
                "2. Подождите 5-10 минут (банки могут задерживать)\n"
                "3. Напишите в поддержку с ID платежа\n"
                "4. Приложите скриншот списания\n"
                "⚡ Решается в течение 2 часов\n\n"
                
                "**🤖 AI дает неточные ответы:**\n"
                "• Переформулируйте вопрос более подробно\n"
                "• Укажите конкретный регион\n"
                "• Добавьте больше деталей ситуации\n"
                "• Задайте уточняющие вопросы\n"
                "• При сложных спорах — обратитесь к живому юристу\n\n"
                
                "**📄 Созданный документ содержит ошибки:**\n"
                "• Проверьте правильность введенных данных\n"
                "• Используйте функцию «Редактировать документ»\n"
                "• Попросите AI внести исправления\n"
                "• Для важных документов — покажите юристу\n\n"
                
                "**📊 Анализ документа неполный:**\n"
                "• Убедитесь, что документ читаемый\n"
                "• Попробуйте другой формат файла\n"
                "• Для сканов — улучшите качество изображения\n"
                "• Можете вставить текст документа вручную\n\n"
                
                "**🔄 Лимиты исчерпаны раньше времени:**\n"
                "• Проверьте дату окончания подписки\n"
                "• Учитывайте, что лимиты обновляются в дату продления\n"
                "• Рассмотрите повышение тарифа\n"
                "• Обратитесь в поддержку для проверки\n\n"
                
                "**📞 Когда обращаться в поддержку:**\n"
                "• Технические сбои и ошибки\n"
                "• Проблемы с оплатой\n"
                "• Вопросы по тарифам\n"
                "• Предложения по улучшению\n"
                "• Любые неясности в работе бота"
            )
        },
        
        "technology": {
            "title": "🤖 **О технологии AI-Юрист**",
            "content": (
                "**Современные технологии для юридической помощи:**\n\n"
                
                "**🧠 Искусственный интеллект:**\n"
                "• **Модель:** GigaChat от Сбера\n"
                "• **Обучение:** российское законодательство\n"
                "• **Языки:** русский (основной)\n"
                "• **Контекст:** до 8000 токенов\n"
                "• **Обновления:** регулярные улучшения\n\n"
                
                "**⚡ Производительность:**\n"
                "• **Время ответа:** 15-90 секунд\n"
                "• **Доступность:** 99.5% времени\n"
                "• **Нагрузка:** до 1000 запросов одновременно\n"
                "• **Серверы:** размещены в России\n\n"
                
                "**📊 Обработка документов:**\n"
                "• **OCR:** распознавание текста с изображений\n"
                "• **Форматы:** PDF, DOC, DOCX, JPG, PNG\n"
                "• **Размер:** до 10 МБ на файл\n"
                "• **Точность:** 95%+ для четких документов\n\n"
                
                "**🔄 Постоянные улучшения:**\n"
                "• Анализ качества ответов\n"
                "• Обратная связь от пользователей\n"
                "• Дообучение на новых данных\n"
                "• Обновление промптов и алгоритмов\n\n"
                
                "**🚀 В разработке:**\n"
                "• Голосовые консультации\n"
                "• Интеграция с госуслугами\n"
                "• Мобильное приложение\n"
                "• API для разработчиков\n"
                "• Расширенная аналитика\n\n"
                
                "**🏆 Преимущества российской AI:**\n"
                "• Знание местного законодательства\n"
                "• Понимание российских реалий\n"
                "• Соответствие требованиям регуляторов\n"
                "• Данные не покидают территорию РФ"
            )
        },
        
        "contacts": {
            "title": "📞 **Контакты и поддержка**",
            "content": (
                "**Мы всегда готовы помочь:**\n\n"
                
                "**💬 Техническая поддержка:**\n"
                "• **Время ответа:** до 3 часов (рабочие дни)\n"
                "• **Режим работы:** Пн-Пт 9:00-18:00 (МСК)\n"
                "• **Язык поддержки:** русский\n\n"
                
                "**🎯 С чем помогаем:**\n"
                "• Технические проблемы и ошибки\n"
                "• Вопросы по оплате\n"
                "• Консультации по тарифам\n"
                "• Обучение работе с ботом\n"
                "• Предложения по улучшению\n\n"
                
                "**📋 Для быстрого решения укажите:**\n"
                "• Ваш Telegram ID (можно узнать у @userinfobot)\n"
                "• Описание проблемы\n"
                "• Скриншоты ошибок (если есть)\n"
                "• ID платежа (для финансовых вопросов)\n"
                "• Время возникновения проблемы\n\n"
                
                "**⚡ Экстренные случаи:**\n"
                "• Списание без активации подписки\n"
                "• Потеря доступа к аккаунту\n"
                "• Критические ошибки в работе\n\n"
                                
                "**📈 Обратная связь:**\n"
                "• Оценки качества консультаций\n"
                "• Предложения новых функций\n"
                "• Сообщения об ошибках\n"
                "• Идеи по улучшению UX"
                
            )
        }
    }
    
    if section in help_sections:
        section_data = help_sections[section]
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к разделам", callback_data="detailed_help")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ]
        
        # Для раздела контактов добавляем кнопку связи с поддержкой
        if section == "contacts":
            keyboard.insert(0, [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/AI_support_users")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            f"{section_data['title']}\n\n{section_data['content']}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # Если раздел не найден, возвращаемся к главному меню справки
        await show_detailed_help(update, context)


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик кнопок главного меню
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_consult":
        # Переход к юридической консультации
        consultation_text = (
            "💬 **Юридическая консультация**\n\n"
            "📋 Получите профессиональный ответ от AI-юриста по любому правовому вопросу\n\n"
            
            "🎯 **Доступные категории:**\n"
            "• Гражданское право\n"
            "• Уголовное право\n"
            "• Семейное право\n"
            "• Трудовое право\n"
            "• Жилищное право\n"
            "• Административное право\n\n"
            
            "💡 **Особенности:**\n"
            "• Ответы со ссылками на законы РФ\n"
            "• Возможность уточняющих вопросов\n"
            "• Сохранение контекста диалога\n\n"
            
            "Для начала консультации используйте:"
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Начать консультацию", callback_data="start_consult")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            consultation_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    elif query.data == "menu_create":
        # Переход к созданию документов
        create_text = (
            "📄 **Создание документов**\n\n"
            "📝 Автоматическое составление готовых юридических документов за 5 минут\n\n"
            
            "📋 **Типы документов (40+ вариантов):**\n"
            "• Договоры (аренды, купли-продажи, услуг)\n"
            "• Исковые заявления (споры, взыскания)\n"
            "• Досудебные претензии\n"
            "• Соглашения и доверенности\n"
            "• Заявления и протоколы\n\n"
            
            "⚡ **Процесс:**\n"
            "• Выбор типа документа\n"
            "• Ответы на 5-7 вопросов\n"
            "• Автогенерация через ИИ\n"
            "• Редактирование и экспорт в Word\n\n"
            
            "Для создания документа используйте:"
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Создать документ", callback_data="start_create")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            create_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    elif query.data == "menu_analyze":
        # Переход к анализу документов
        analyze_text = (
            "📊 **Анализ документов**\n\n"
            "🔍 Профессиональная проверка и экспертное заключение по вашим документам\n\n"
            
            "📄 **Поддерживаемые форматы:**\n"
            "• Документы: DOC, DOCX, PDF\n"
            "• Изображения: JPG, PNG (сканы)\n"
            "• Максимальный размер: 10 МБ\n\n"
            
            "🎯 **Типы анализа:**\n"
            "• Соответствие закону\n"
            "• Поиск ошибок и недочетов\n"
            "• Оценка правовых рисков\n"
            "• Рекомендации по улучшению\n"
            "• Анализ деловой переписки\n\n"
            
            "Для начала анализа используйте:"
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Начать анализ", callback_data="start_analyze")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            analyze_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    elif query.data == "menu_help":
        # Справка и поддержка
        help_text_short = (
            "📚 **Краткая справка**\n\n"
            
            "🎯 **Доступные услуги:**\n"
            "• 💬 Консультации по праву\n"
            "• 📄 Создание документов\n"
            "• 📊 Анализ документов\n\n"
            
            "🎛️ **Как пользоваться:**\n"
            "Используйте кнопки в главном меню для выбора нужной услуги"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Подробная справка", callback_data="detailed_help")],
            [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/AI_support_users")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            help_text_short,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == "back_to_main" or query.data == "main_menu":
        # Возврат в главное меню с персонализацией
        user = update.effective_user
        if user:
            telegram_id = user.id
            user_name = user.first_name if user.first_name else "пользователь"
            message_text, keyboard = await get_personalized_main_menu(telegram_id, user_name)
        else:
            user_name = "пользователь"
            message_text, keyboard = get_default_menu(user_name)
        
        await query.message.reply_text(
            message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif query.data == "notify_analyze":
        # Уведомление о готовности анализа
        await query.message.reply_text(
            "🔔 **Уведомление настроено!**\n\n"
            "Мы обязательно сообщим вам, когда функция анализа документов будет готова.\n\n"
            "📧 Уведомление придет в этот чат\n"
            "⏰ Ожидаемый срок: 2-3 недели"
        )
    
    elif query.data == "start_analyze":
        # Запуск анализа документов
        await analyze_command(update, context)
    
    elif query.data == "analyze":
        # Запуск анализа документов (из кнопки после создания документа)
        await analyze_command(update, context)
    
    elif query.data == "detailed_help":
        # Подробная справка
        await show_detailed_help(update, context)
    
    elif query.data == "subscription_menu":
        # Переход к подпискам
        await subscription_command(update, context)
    
    # Обработчики разделов подробной справки
    elif query.data.startswith("help_"):
        await handle_help_section(update, context)
    
    # Обработка подписок
    elif query.data in subscription_handlers:
        handler = subscription_handlers[query.data]
        await handler(update, context)
    
    elif query.data.startswith("check_payment_"):
        await check_payment_status(update, context)


def main() -> None:
    """
    Основная функция запуска бота
    """
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ConversationHandler для консультаций
    consultation_handler = ConversationHandler(
        entry_points=[
            CommandHandler('consult', consult_command),
            CallbackQueryHandler(lambda update, context: consult_command(update, context), pattern='^start_consult$')
        ],
        states={
            ConsultationStates.CATEGORY_SELECTION.value: [
                CallbackQueryHandler(category_selected, pattern='^category_'),
                CallbackQueryHandler(back_to_categories, pattern='^back_to_categories$'),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            ConsultationStates.WAITING_QUESTION.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_question),
                CallbackQueryHandler(back_to_categories, pattern='^back_to_categories$'),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            ConsultationStates.CONSULTATION_DIALOG.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_dialog_message),
                CallbackQueryHandler(continue_consultation, pattern='^continue_consultation$'),
                CallbackQueryHandler(continue_dialog, pattern='^continue_dialog$'),
                CallbackQueryHandler(end_consultation, pattern='^end_consultation$'),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel_consultation)],
        allow_reentry=True
    )
    
    # ConversationHandler для создания документов
    document_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("create", create_command),
            CallbackQueryHandler(lambda update, context: create_command(update, context), pattern='^start_create$')
        ],
        states={
            DocumentStates.DOCUMENT_TYPE_SELECTION.value: [
                CallbackQueryHandler(document_type_selected, pattern="^doctype_"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_SUBTYPE_SELECTION.value: [
                CallbackQueryHandler(document_subtype_selected, pattern="^docsubtype_"),
                CallbackQueryHandler(back_to_types, pattern="^back_to_types$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DATA_COLLECTION.value: [
                CallbackQueryHandler(start_data_collection, pattern="^start_data_collection$"),
                CallbackQueryHandler(process_answer, pattern="^answer_"),
                CallbackQueryHandler(process_answer, pattern="^custom_answer$"),
                CallbackQueryHandler(process_answer, pattern="^prev_question$"),
                CallbackQueryHandler(cancel_custom_answer, pattern="^cancel_custom$"),
                CallbackQueryHandler(back_to_subtypes, pattern="^back_to_subtypes$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_answer),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_GENERATION.value: [
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_REVIEW.value: [
                CallbackQueryHandler(handle_document_review, pattern="^accept_document$"),
                CallbackQueryHandler(handle_document_review, pattern="^edit_document$"),
                CallbackQueryHandler(handle_document_review, pattern="^supplement_document$"),
                CallbackQueryHandler(handle_document_review, pattern="^regenerate_document$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_EDITING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_document_changes),
                CallbackQueryHandler(start_document_editing, pattern="^edit_document$"),
                CallbackQueryHandler(start_document_supplement, pattern="^supplement_document$"),
                CallbackQueryHandler(cancel_edit, pattern="^cancel_edit$"),
                CallbackQueryHandler(cancel_supplement, pattern="^cancel_supplement$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_FINALIZATION.value: [
                CallbackQueryHandler(handle_document_rating, pattern="^rate_"),
                CallbackQueryHandler(handle_document_rating, pattern="^skip_rating$"),
                CallbackQueryHandler(create_command, pattern="^new_document$"),
                CallbackQueryHandler(lambda update, context: analyze_command(update, context), pattern="^analyze$"),
                CallbackQueryHandler(consult_command, pattern="^consultation$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(cancel_document_creation, pattern="^cancel_"),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ]
    )
    
    # ConversationHandler для анализа документов
    analysis_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("analyze", analyze_command),
            CallbackQueryHandler(lambda update, context: analyze_command(update, context), pattern='^start_analyze$')
        ],
        states={
            AnalysisStates.DOCUMENT_UPLOAD.value: [
                MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document_upload),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^retry_upload$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^back_to_upload$"),
                CallbackQueryHandler(cancel_analysis, pattern="^cancel_analysis$")
            ],
            AnalysisStates.MULTIPLE_IMAGES.value: [
                MessageHandler(filters.PHOTO, handle_document_upload),  # Для добавления новых изображений
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^add_more_images$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^process_single_image$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^process_all_images$"),
                CallbackQueryHandler(cancel_analysis, pattern="^cancel_analysis$")
            ],
            AnalysisStates.ANALYSIS_TYPE_SELECTION.value: [
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^analysis_type_"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^start_analysis$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^back_to_analysis_types$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^change_analysis_type$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^back_to_menu$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^retry_upload$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^back_to_upload$"),
                CallbackQueryHandler(cancel_analysis, pattern="^cancel_analysis$")
            ],
            AnalysisStates.TEXT_PROCESSING.value: [
                # Промежуточное состояние, автоматически переходит дальше
            ],
            AnalysisStates.ANALYSIS_PROCESSING.value: [
                # Промежуточное состояние, автоматически переходит дальше
            ],
            AnalysisStates.RESULTS_REVIEW.value: [
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^back_to_analysis_types$"),
                CallbackQueryHandler(handle_analysis_type_selection, pattern="^change_analysis_type$"),
                CallbackQueryHandler(handle_additional_actions, pattern="^upload_new_document$"),
                CallbackQueryHandler(handle_additional_actions, pattern="^finish_analysis$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(cancel_analysis, pattern="^cancel_analysis$"),
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ]
    )
    
    # Регистрируем обработчики
    # ConversationHandler для подписок
    subscription_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('subscription', subscription_command),
            CallbackQueryHandler(subscription_command, pattern='^subscription_menu$')
        ],
        states={
            SubscriptionStates.SUBSCRIPTION_SELECTION.value: [
                CallbackQueryHandler(activate_trial_subscription, pattern='^activate_trial$'),
                CallbackQueryHandler(initiate_subscription_payment, pattern='^subscribe_'),
                CallbackQueryHandler(initiate_subscription_payment, pattern='^upgrade_(basic|premium|corporate)$'),
                CallbackQueryHandler(main_menu_handler, pattern='^main_menu$')
            ],
            SubscriptionStates.PAYMENT_PROCESSING.value: [
                CallbackQueryHandler(check_payment_status, pattern='^check_payment_'),
                CallbackQueryHandler(cancel_payment, pattern='^cancel_payment$'),
                CallbackQueryHandler(main_menu_handler, pattern='^main_menu$')
            ],
            SubscriptionStates.SUBSCRIPTION_MANAGEMENT.value: [
                CallbackQueryHandler(initiate_subscription_payment, pattern='^upgrade_(basic|premium|corporate)$'),
                CallbackQueryHandler(show_upgrade_menu, pattern='^upgrade_menu$'),
                CallbackQueryHandler(show_trial_upgrade_menu, pattern='^trial_upgrade_menu$'),
                CallbackQueryHandler(renew_subscription, pattern='^renew_subscription$'),
                CallbackQueryHandler(main_menu_handler, pattern='^main_menu$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', main_menu_handler),
            CallbackQueryHandler(main_menu_handler, pattern='^main_menu$')
        ],
        allow_reentry=True
    )

    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('subscription', subscription_command))
    application.add_handler(consultation_handler)
    application.add_handler(document_conv_handler)
    application.add_handler(analysis_conv_handler)
    application.add_handler(subscription_conv_handler)
    
    # Обработчик для callback query вне conversations
    application.add_handler(CallbackQueryHandler(main_menu_handler))
    
    # Запускаем бота
    logger.info("Запуск AI-юрист бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main() 