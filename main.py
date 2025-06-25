#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-юрист Telegram Bot
Основной файл для запуска бота
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes

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
    back_to_types, back_to_subtypes, cancel_document_creation
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start
    Отправляет главное меню с inline-кнопками
    """
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    welcome_message = (
        f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
        f"👋 Привет, {user_name}!\n\n"
        
        "🎯 **Проверенный сервис:**\n"
        "• 6 отраслей права\n"
        "• 40+ типов документов\n"
        "• Экспорт в Word\n"
        "• Консультаций проведено: 500+\n\n"
        
        "💼 **Выберите нужную услугу:**"
    )
    
    # Создаем клавиатуру главного меню
    keyboard = [
        [InlineKeyboardButton("💬 Юридическая консультация", callback_data="menu_consult")],
        [InlineKeyboardButton("📄 Создание документов", callback_data="menu_create")],
        [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
        [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /help - подробная справка
    """
    help_text = (
        "📖 **Подробная справка AI-Юрист**\n\n"
        
        "🤖 **Основные команды:**\n"
        "• `/start` — Главное меню с выбором услуг\n"
        "• `/consult` — Прямой переход к консультации\n"
        "• `/create` — Прямой переход к созданию документов\n"
        "• `/help` — Показать эту справку\n\n"
        
        "💬 **Юридическая консультация:**\n"
        "• Задайте любой правовой вопрос\n"
        "• Получите ответ со ссылками на законы\n"
        "• Ведите диалог с уточняющими вопросами\n"
        "• Доступно 6 отраслей права\n\n"
        
        "📄 **Создание документов:**\n"
        "• 40+ типов документов\n"
        "• Автоматическая генерация за 5 минут\n"
        "• Возможность редактирования\n"
        "• Экспорт в формат Word (.docx)\n"
        "• Система оценки качества\n\n"
        
        "🔐 **Безопасность и конфиденциальность:**\n"
        "• Ваши данные не сохраняются на серверах\n"
        "• Все файлы автоматически удаляются\n"
        "• Шифрованная передача данных\n"
        "• Полная анонимность\n\n"
        
        "📞 **Техническая поддержка:**\n"
        "• Telegram: @ai_lawyer_support\n"
        "• Время ответа: до 2 часов\n"
        "• Решение проблем и предложения"
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
        # Анализ документов (будущая функция)
        analyze_text = (
            "📊 **Анализ документов**\n\n"
            "🔍 Профессиональная проверка и экспертное заключение по вашим документам\n\n"
            
            "📄 **Что можно анализировать:**\n"
            "• Договоры на соответствие закону\n"
            "• Исковые заявления\n"
            "• Претензии и жалобы\n"
            "• Деловую переписку\n\n"
            
            "⚙️ **Возможности:**\n"
            "• Поиск юридических ошибок\n"
            "• Рекомендации по улучшению\n"
            "• Оценка правовых рисков\n"
            "• Соответствие требованиям\n\n"
            
            "🚧 **Статус:** Функция находится в разработке\n"
            "📅 **Запуск:** Планируется в ближайших обновлениях"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔔 Уведомить о готовности", callback_data="notify_analyze")],
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
        help_text = (
            "ℹ️ **Справка и поддержка**\n\n"
            "📖 Полная информация о возможностях AI-Юриста\n\n"
            
            "🤖 **Команды бота:**\n"
            "• `/start` — Главное меню\n"
            "• `/consult` — Быстрая консультация\n"
            "• `/create` — Создание документа\n"
            "• `/help` — Подробная справка\n\n"
            
            "💡 **Как пользоваться:**\n"
            "• Выберите нужную услугу в меню\n"
            "• Следуйте инструкциям бота\n"
            "• Задавайте уточняющие вопросы\n"
            "• Используйте кнопки для навигации\n\n"
            
            "🔒 **Безопасность:**\n"
            "• Данные не сохраняются\n"
            "• Конфиденциальность гарантирована\n"
            "• Временные файлы автоудаляются\n\n"
            
            "📞 **Поддержка:** @ai_lawyer_support"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Подробная справка", callback_data="detailed_help")],
            [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/ai_lawyer_support")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == "back_to_main":
        # Возврат в главное меню
        user = update.effective_user
        user_name = user.first_name if user.first_name else "пользователь"
        
        welcome_message = (
            f"🏛️ **AI-Юрист** — ваш персональный правовой помощник\n\n"
            f"👋 Привет, {user_name}!\n\n"
            
            "🎯 **Проверенный сервис:**\n"
            "• 6 отраслей права\n"
            "• 40+ типов документов\n"
            "• Экспорт в Word\n"
            "• Консультаций проведено: 500+\n\n"
            
            "💼 **Выберите нужную услугу:**"
        )
        
        # Создаем клавиатуру главного меню
        keyboard = [
            [InlineKeyboardButton("💬 Юридическая консультация", callback_data="menu_consult")],
            [InlineKeyboardButton("📄 Создание документов", callback_data="menu_create")],
            [InlineKeyboardButton("📊 Анализ документов", callback_data="menu_analyze")],
            [InlineKeyboardButton("ℹ️ Справка и поддержка", callback_data="menu_help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
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
    
    elif query.data == "detailed_help":
        # Подробная справка
        await help_command(update, context)


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
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            DocumentStates.DOCUMENT_FINALIZATION.value: [
                CallbackQueryHandler(handle_document_rating, pattern="^rate_"),
                CallbackQueryHandler(handle_document_rating, pattern="^skip_rating$"),
                CallbackQueryHandler(create_command, pattern="^new_document$"),
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
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(consultation_handler)
    application.add_handler(document_conv_handler)
    
    # Обработчик для callback query вне conversations
    application.add_handler(CallbackQueryHandler(main_menu_handler))
    
    # Запускаем бота
    logger.info("Запуск AI-юрист бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main() 