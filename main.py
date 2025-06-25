#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-юрист Telegram Bot
Основной файл для запуска бота
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN
from bot.handlers import (
    consult_command, category_selected, process_question, 
    back_to_categories, cancel_consultation, ConsultationStates,
    main_menu_callback, continue_consultation, process_dialog_message,
    continue_dialog, end_consultation
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
    Отправляет приветственное сообщение с доступными командами
    """
    welcome_message = (
        "🤖 Добро пожаловать в AI-юриста!\n\n"
        "Доступные команды:\n"
        "• /consult - Юридические консультации\n"
        "• /create - Создание документов\n"
        "• /analyze - Анализ документов\n"
        "• /subscribe - Оформление подписки\n\n"
        "Для начала работы выберите нужную команду."
    )
    
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /help
    """
    help_text = (
        "📚 Справка по командам:\n\n"
        "🔹 /start - Главное меню\n"
        "🔹 /consult - Получить юридическую консультацию\n"
        "🔹 /create - Создать юридический документ\n"
        "🔹 /analyze - Проанализировать документ\n"
        "🔹 /subscribe - Управление подпиской\n"
        "🔹 /help - Показать эту справку\n\n"
        "❓ При возникновении проблем обратитесь в поддержку."
    )
    
    await update.message.reply_text(help_text)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Общий обработчик callback query для кнопок вне ConversationHandler
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "main_menu":
        # Возврат в главное меню
        await main_menu_callback(update, context)
    elif query.data == "new_consultation":
        # Запуск новой консультации
        await query.message.reply_text(
            "🔄 Запускаем новую консультацию...\n"
            "Используйте команду /consult"
        )
    elif query.data == "create_document":
        # Переход к созданию документа
        await query.message.reply_text(
            "📄 Для создания документа используйте команду /create\n"
            "(Функция будет доступна в следующих обновлениях)"
        )
    elif query.data == "rate_answer":
        # Оценка ответа
        await query.message.reply_text(
            "⭐ Спасибо за обратную связь!\n"
            "Ваша оценка поможет нам улучшить качество консультаций."
        )
    elif query.data == "contact_lawyer":
        # Связь с юристом
        await query.message.reply_text(
            "📞 Для связи с юристом используйте команду /subscribe\n"
            "и оформите расширенную подписку."
        )


def main() -> None:
    """
    Основная функция запуска бота
    """
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ConversationHandler для консультаций
    consultation_handler = ConversationHandler(
        entry_points=[CommandHandler('consult', consult_command)],
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
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(consultation_handler)
    
    # Обработчик для callback query вне conversations
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Запускаем бота
    logger.info("Запуск AI-юрист бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main() 