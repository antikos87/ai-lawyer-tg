#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики команд Telegram бота
"""

import logging
from enum import Enum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # type: ignore
from telegram.ext import ContextTypes, ConversationHandler  # type: ignore
from telegram.constants import ChatAction  # type: ignore
from ai_gigachat.client import gigachat_client

logger = logging.getLogger(__name__)


class ConsultationStates(Enum):
    """Состояния диалога консультации"""
    CATEGORY_SELECTION = 0
    WAITING_QUESTION = 1
    PROCESSING = 2
    CONSULTATION_DIALOG = 3


async def consult_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /consult
    Запускает диалог юридической консультации
    """
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    # Приветственное сообщение
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        "🎓 Я AI-юрист и помогу вам с юридическими вопросами.\n"
        "📋 Выберите тип консультации или задайте свой вопрос напрямую:\n\n"
        "💡 Я могу:\n"
        "• Объяснить правовые нормы простым языком\n"
        "• Дать рекомендации по дальнейшим действиям\n"
        "• Помочь разобраться в документах\n\n"
        "Выберите категорию ниже или напишите свой вопрос:"
    )
    
    # Inline клавиатура с категориями
    keyboard = [
        [
            InlineKeyboardButton("⚖️ Гражданское право", callback_data="category_civil"),
            InlineKeyboardButton("🔒 Уголовное право", callback_data="category_criminal")
        ],
        [
            InlineKeyboardButton("👨‍👩‍👧‍👦 Семейное право", callback_data="category_family"),
            InlineKeyboardButton("💼 Трудовое право", callback_data="category_labor")
        ],
        [
            InlineKeyboardButton("🏠 Жилищное право", callback_data="category_housing"),
            InlineKeyboardButton("🚗 Административное право", callback_data="category_admin")
        ],
        [
            InlineKeyboardButton("❓ Другое", callback_data="category_other")
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Проверяем, вызвано ли из callback query или обычного message
    if update.callback_query:
        # Вызвано из callback query (например, из главного меню)
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
    else:
        # Вызвано из обычного сообщения (команда /consult)
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
    
    return ConsultationStates.CATEGORY_SELECTION.value


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора категории консультации
    """
    query = update.callback_query
    await query.answer()
    
    # Сохраняем выбранную категорию
    category_map = {
        "category_civil": "Гражданское право",
        "category_criminal": "Уголовное право", 
        "category_family": "Семейное право",
        "category_labor": "Трудовое право",
        "category_housing": "Жилищное право",
        "category_admin": "Административное право",
        "category_other": "Другое"
    }
    
    selected_category = category_map.get(query.data, "Другое")
    context.user_data['consultation_category'] = selected_category
    
    # Сообщение с запросом вопроса
    question_text = (
        f"📝 Выбрана категория: **{selected_category}**\n\n"
        "Теперь опишите вашу ситуацию максимально подробно:\n\n"
        "📌 Укажите:\n"
        "• Суть проблемы\n"
        "• Какие документы у вас есть\n"
        "• Что уже предпринимали\n"
        "• Какой результат хотите получить\n\n"
        "✍️ Напишите ваш вопрос:"
    )
    
    # Кнопки навигации
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="back_to_categories")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        question_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConsultationStates.WAITING_QUESTION.value


async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик вопроса пользователя
    """
    user_question = update.message.text
    category = context.user_data.get('consultation_category', 'Общее')
    
    # Сохраняем вопрос пользователя
    context.user_data['user_question'] = user_question
    
    # Отправляем индикатор "печатает"
    await update.message.chat.send_action(ChatAction.TYPING)
    
    # Подтверждение получения запроса
    status_message = await update.message.reply_text(
        "📤 Ваш запрос принят!\n"
        "🔍 Анализирую информацию и готовлю подробный ответ...\n\n"
        "⏱️ Это займёт несколько секунд."
    )
    
    # Генерируем ответ через GigaChat API
    try:
        # Используем GigaChat для генерации ответа
        answer = await gigachat_client.generate_consultation(
            user_question=user_question,
            category=category
        )
        
        # Удаляем сообщение о статусе
        await status_message.delete()
        
        # Добавляем первый ответ в историю
        if 'consultation_history' not in context.user_data:
            context.user_data['consultation_history'] = []
        
        context.user_data['consultation_history'].extend([
            {
                'role': 'user',
                'content': user_question,
                'timestamp': update.message.date
            },
            {
                'role': 'assistant', 
                'content': answer,
                'timestamp': update.message.date
            }
        ])
        
        # Отправляем ответ
        await send_consultation_answer(update, answer, category)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке консультации: {e}")
        await status_message.edit_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте ёще раз или обратитесь в поддержку."
        )
    
    return ConsultationStates.CONSULTATION_DIALOG.value


async def generate_consultation_answer(question: str, category: str) -> str:
    """
    Генерация ответа на юридический вопрос через GigaChat API
    """
    try:
        # Используем GigaChat для генерации ответа
        answer = await gigachat_client.generate_consultation(
            user_question=question,
            category=category
        )
        return answer
        
    except Exception as e:
        logger.error(f"Ошибка при генерации ответа через GigaChat: {e}")
        
        # Резервный ответ при ошибке
        return (
            f"📋 **Консультация по категории: {category}**\n\n"
            f"❓ **Ваш вопрос:** {question[:100]}{'...' if len(question) > 100 else ''}\n\n"
            "❌ **Извините, возникла техническая ошибка**\n\n"
            "Наша система временно недоступна. Попробуйте:\n\n"
            "🔄 **Что можно сделать:**\n"
            "• Переформулировать вопрос и попробовать снова\n"
            "• Использовать команду /consult через несколько минут\n"
            "• Обратиться в службу поддержки\n\n"
            "📞 **При срочных вопросах** рекомендуем обратиться к практикующему юристу.\n\n"
            "❓ Попробуйте /consult снова через несколько минут."
        )


async def send_consultation_answer(update: Update, answer: str, category: str) -> None:
    """
    Отправка ответа консультации с опциями продолжения беседы
    """
    # Кнопки для продолжения беседы
    keyboard = [
        [
            InlineKeyboardButton("💬 Продолжить консультацию", callback_data="continue_consultation"),
        ],
        [
            InlineKeyboardButton("📝 Новая консультация", callback_data="new_consultation"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        answer,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Возврат к выбору категорий
    """
    query = update.callback_query
    await query.answer()
    
    # Повторно показываем категории
    return await consult_command_from_callback(query, context)


async def consult_command_from_callback(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запуск консультации из callback
    """
    user = query.from_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    welcome_text = (
        f"👋 Привет, {user_name}!\n\n"
        "🎓 Выберите тип консультации:"
    )
    
    # Inline клавиатура с категориями
    keyboard = [
        [
            InlineKeyboardButton("⚖️ Гражданское право", callback_data="category_civil"),
            InlineKeyboardButton("🔒 Уголовное право", callback_data="category_criminal")
        ],
        [
            InlineKeyboardButton("👨‍👩‍👧‍👦 Семейное право", callback_data="category_family"),
            InlineKeyboardButton("💼 Трудовое право", callback_data="category_labor")
        ],
        [
            InlineKeyboardButton("🏠 Жилищное право", callback_data="category_housing"),
            InlineKeyboardButton("🚗 Административное право", callback_data="category_admin")
        ],
        [
            InlineKeyboardButton("❓ Другое", callback_data="category_other")
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        welcome_text,
        reply_markup=reply_markup
    )
    
    return ConsultationStates.CATEGORY_SELECTION.value


async def cancel_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена консультации
    """
    await update.message.reply_text(
        "❌ Консультация отменена.\n"
        "Для новой консультации используйте /consult"
    )
    return ConversationHandler.END


async def continue_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Переход в режим продолжения консультации
    """
    query = update.callback_query
    await query.answer()
    
    category = context.user_data.get('consultation_category', 'Общее')
    
    # Инициализируем историю диалога, если её нет
    if 'consultation_history' not in context.user_data:
        context.user_data['consultation_history'] = []
    
    continue_text = (
        f"💬 **Продолжаем консультацию по категории: {category}**\n\n"
        "Задайте уточняющий вопрос или опишите новые обстоятельства.\n"
        "Я учту контекст нашей предыдущей беседы.\n\n"
        "✍️ Напишите ваш вопрос:"
    )
    
    # Кнопки для управления диалогом
    keyboard = [
        [
            InlineKeyboardButton("✅ Завершить консультацию", callback_data="end_consultation"),
        ],
        [
            InlineKeyboardButton("📝 Новая консультация", callback_data="new_consultation"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        continue_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConsultationStates.CONSULTATION_DIALOG.value


async def process_dialog_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик сообщений в режиме диалога консультации
    """
    user_question = update.message.text
    category = context.user_data.get('consultation_category', 'Общее')
    
    # Получаем историю диалога
    consultation_history = context.user_data.get('consultation_history', [])
    
    # Добавляем новый вопрос пользователя в историю
    consultation_history.append({
        'role': 'user',
        'content': user_question,
        'timestamp': update.message.date
    })
    
    # Отправляем индикатор "печатает"
    await update.message.chat.send_action(ChatAction.TYPING)
    
    # Подтверждение получения запроса
    status_message = await update.message.reply_text(
        "💬 Продолжаем консультацию...\n"
        "🔍 Анализирую ваш вопрос с учётом контекста беседы...\n\n"
        "⏱️ Это займёт несколько секунд."
    )
    
    # Генерируем ответ через GigaChat API с учётом истории
    try:
        # Формируем контекст из истории
        context_data = {
            'consultation_history': consultation_history,
            'is_continuation': True
        }
        
        # Используем GigaChat для генерации ответа
        answer = await gigachat_client.generate_consultation(
            user_question=user_question,
            category=category,
            user_context=context_data
        )
        
        # Добавляем ответ бота в историю
        consultation_history.append({
            'role': 'assistant',
            'content': answer,
            'timestamp': update.message.date
        })
        
        # Сохраняем обновлённую историю
        context.user_data['consultation_history'] = consultation_history
        
        # Удаляем сообщение о статусе
        await status_message.delete()
        
        # Отправляем ответ с кнопками продолжения диалога
        await send_dialog_answer(update, answer, category)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке диалога консультации: {e}")
        await status_message.edit_text(
            "❌ Произошла ошибка при обработке запроса.\n"
            "Попробуйте ещё раз или начните новую консультацию."
        )
    
    return ConsultationStates.CONSULTATION_DIALOG.value


async def send_dialog_answer(update: Update, answer: str, category: str) -> None:
    """
    Отправка ответа в режиме диалога консультации
    """
    # Кнопки для продолжения диалога
    keyboard = [
        [
            InlineKeyboardButton("💬 Продолжить диалог", callback_data="continue_dialog"),
        ],
        [
            InlineKeyboardButton("✅ Завершить консультацию", callback_data="end_consultation"),
        ],
        [
            InlineKeyboardButton("📝 Новая консультация", callback_data="new_consultation"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        answer,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def continue_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Продолжение диалога в консультации
    """
    query = update.callback_query
    await query.answer()
    
    category = context.user_data.get('consultation_category', 'Общее')
    
    continue_text = (
        f"💬 **Продолжаем диалог по категории: {category}**\n\n"
        "Задайте следующий вопрос или уточните детали.\n\n"
        "✍️ Напишите ваше сообщение:"
    )
    
    # Кнопки для управления диалогом
    keyboard = [
        [
            InlineKeyboardButton("✅ Завершить консультацию", callback_data="end_consultation"),
        ],
        [
            InlineKeyboardButton("📝 Новая консультация", callback_data="new_consultation"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        continue_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConsultationStates.CONSULTATION_DIALOG.value


async def end_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Завершение консультации
    """
    query = update.callback_query
    await query.answer()
    
    # Очищаем историю консультации
    context.user_data.pop('consultation_history', None)
    context.user_data.pop('consultation_category', None)
    context.user_data.pop('user_question', None)
    
    end_text = (
        "✅ **Консультация завершена**\n\n"
        "Спасибо за обращение к AI-юристу!\n\n"
        "💡 **Напоминаем:**\n"
        "• Данная консультация носит информационный характер\n"
        "• При сложных вопросах рекомендуем обратиться к практикующему юристу\n"
        "• Сохраните важную информацию из нашей беседы\n\n"
        "Для новой консультации используйте /consult"
    )
    
    await query.message.reply_text(
        end_text,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик возврата в главное меню с inline-кнопками
    """
    query = update.callback_query
    await query.answer()
    
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
    
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда помощи - показывает доступные команды"""
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    help_text = f"""
👋 Привет, {user_name}!

🤖 **AI Lawyer Bot** - ваш персональный юридический помощник

📋 **Доступные команды:**

/start - Начать работу с ботом
/help - Показать эту справку
/consult - Получить юридическую консультацию
/create - Создать юридический документ

💡 **Возможности бота:**

🔹 **Консультации** - получите профессиональные ответы на правовые вопросы по различным отраслям права
🔹 **Создание документов** - автоматическое составление договоров, исков, претензий и других юридических документов
🔹 **Экспорт в Word** - готовые документы в формате .docx для дальнейшего использования

📞 **Поддержка:** @your_support_bot
"""
    
    await update.message.reply_text(help_text)