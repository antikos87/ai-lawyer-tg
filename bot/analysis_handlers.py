#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для анализа юридических документов
"""

import logging
import os
import tempfile
import re
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction

# Импорты для извлечения текста
import fitz  # PyMuPDF
from docx import Document as DocxDocument
import pytesseract
from PIL import Image
import PyPDF2

from ai_gigachat.client import gigachat_client

logger = logging.getLogger(__name__)


class AnalysisStates(Enum):
    """Состояния диалога анализа документов"""
    DOCUMENT_UPLOAD = 0
    ANALYSIS_TYPE_SELECTION = 1
    TEXT_PROCESSING = 2
    ANALYSIS_PROCESSING = 3
    RESULTS_REVIEW = 4
    ADDITIONAL_ACTIONS = 5


# Поддерживаемые типы файлов
SUPPORTED_EXTENSIONS = {
    'document': ['.doc', '.docx', '.pdf'],
    'image': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
}

# Максимальный размер файла (10 МБ)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Типы анализа (соответствуют ключам в GigaChat клиенте)
ANALYSIS_TYPES = {
    'law_compliance': {
        'name': '⚖️ Проверить соответствие закону',
        'description': 'Проверка документа на соответствие действующему законодательству РФ',
        'icon': '⚖️'
    },
    'error_detection': {
        'name': '🔍 Найти ошибки',
        'description': 'Поиск юридических, технических и логических ошибок в документе',
        'icon': '🔍'
    },
    'risk_assessment': {
        'name': '⚠️ Оценить риски',
        'description': 'Анализ правовых рисков и потенциальных проблем',
        'icon': '⚠️'
    },
    'recommendations': {
        'name': '💡 Дать рекомендации',
        'description': 'Предложения по улучшению и оптимизации документа',
        'icon': '💡'
    },
    'correspondence_analysis': {
        'name': '📧 Анализировать переписку',
        'description': 'Специальный анализ деловой переписки и коммуникаций',
        'icon': '📧'
    }
}


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /analyze - начало анализа документов
    """
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    # Очищаем предыдущие данные
    context.user_data.clear()
    
    welcome_text = (
        f"📊 **Анализ юридических документов**\n\n"
        f"Привет, {user_name}! Я помогу проанализировать ваш документ.\n\n"
        
        "📋 **Поддерживаемые форматы:**\n"
        "• **Документы:** DOC, DOCX, PDF\n"
        "• **Изображения:** JPG, PNG (сканы документов)\n"
        "• **Максимальный размер:** 10 МБ\n\n"
        
        "🎯 **Типы анализа:**\n"
        "• Проверка соответствия закону\n"
        "• Поиск ошибок и недочетов\n"
        "• Оценка правовых рисков\n"
        "• Рекомендации по улучшению\n"
        "• Анализ деловой переписки\n\n"
        
        "📎 **Загрузите документ для анализа:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_analysis")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Определяем откуда пришел запрос
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return AnalysisStates.DOCUMENT_UPLOAD.value


async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик загрузки документа
    """
    # Показываем индикатор обработки
    await update.message.chat.send_action(ChatAction.TYPING)
    
    document = update.message.document
    photo = update.message.photo
    
    # Проверяем что загружен файл
    if not document and not photo:
        await update.message.reply_text(
            "❌ **Ошибка загрузки**\n\n"
            "Пожалуйста, загрузите документ в поддерживаемом формате:\n"
            "• DOC, DOCX, PDF - документы\n"
            "• JPG, PNG - изображения (сканы)\n\n"
            "Максимальный размер файла: 10 МБ",
            parse_mode='Markdown'
        )
        return AnalysisStates.DOCUMENT_UPLOAD.value
    
    # Обработка обычного документа
    if document:
        file_name = document.file_name
        file_size = document.file_size
        file_id = document.file_id
        
        # Проверяем размер файла
        if file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ **Файл слишком большой**\n\n"
                f"Размер файла: {file_size / (1024*1024):.1f} МБ\n"
                f"Максимальный размер: 10 МБ\n\n"
                "Пожалуйста, загрузите файл меньшего размера.",
                parse_mode='Markdown'
            )
            return AnalysisStates.DOCUMENT_UPLOAD.value
        
        # Проверяем расширение файла
        file_extension = os.path.splitext(file_name.lower())[1]
        if file_extension not in SUPPORTED_EXTENSIONS['document']:
            await update.message.reply_text(
                f"❌ **Неподдерживаемый формат**\n\n"
                f"Файл: `{file_name}`\n"
                f"Формат: `{file_extension}`\n\n"
                "Поддерживаемые форматы документов:\n"
                "• DOC, DOCX, PDF\n\n"
                "Пожалуйста, загрузите файл в поддерживаемом формате.",
                parse_mode='Markdown'
            )
            return AnalysisStates.DOCUMENT_UPLOAD.value
        
        file_type = 'document'
        
    # Обработка изображения
    else:  # photo
        # Берем изображение наилучшего качества
        photo_file = photo[-1]
        file_size = photo_file.file_size
        file_id = photo_file.file_id
        file_name = f"image_{photo_file.file_id}.jpg"
        file_extension = '.jpg'
        file_type = 'image'
        
        # Проверяем размер
        if file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ **Изображение слишком большое**\n\n"
                f"Размер: {file_size / (1024*1024):.1f} МБ\n"
                f"Максимальный размер: 10 МБ\n\n"
                "Пожалуйста, загрузите изображение меньшего размера.",
                parse_mode='Markdown'
            )
            return AnalysisStates.DOCUMENT_UPLOAD.value
    
    # Сохраняем информацию о файле
    context.user_data['file_info'] = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': file_size,
        'file_extension': file_extension,
        'file_type': file_type
    }
    
    # Подтверждение загрузки
    success_text = (
        f"✅ **Файл успешно загружен**\n\n"
        f"📄 **Файл:** `{file_name}`\n"
        f"📏 **Размер:** {file_size / 1024:.1f} КБ\n"
        f"📝 **Тип:** {'Документ' if file_type == 'document' else 'Изображение (скан)'}\n\n"
        "Выберите тип анализа:"
    )
    
    # Создаем клавиатуру с типами анализа
    keyboard = []
    for analysis_type, info in ANALYSIS_TYPES.items():
        keyboard.append([InlineKeyboardButton(
            info['name'], 
            callback_data=f"analysis_type_{analysis_type}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_analysis")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        success_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return AnalysisStates.ANALYSIS_TYPE_SELECTION.value


async def handle_analysis_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора типа анализа
    """
    query = update.callback_query
    await query.answer()
    
    # Извлекаем тип анализа
    analysis_type = query.data.replace("analysis_type_", "")
    
    if analysis_type not in ANALYSIS_TYPES:
        await query.message.reply_text("❌ Неизвестный тип анализа")
        return AnalysisStates.ANALYSIS_TYPE_SELECTION.value
    
    # Сохраняем выбранный тип анализа
    context.user_data['analysis_type'] = analysis_type
    analysis_info = ANALYSIS_TYPES[analysis_type]
    
    # Показываем подтверждение выбора
    confirmation_text = (
        f"🎯 **Выбран тип анализа:**\n\n"
        f"{analysis_info['icon']} **{analysis_info['name']}**\n\n"
        f"📋 {analysis_info['description']}\n\n"
        "⏳ Начинаю обработку документа..."
    )
    
    await query.message.reply_text(
        confirmation_text,
        parse_mode='Markdown'
    )
    
    # Переходим к обработке текста
    return await start_text_processing(update, context)


async def start_text_processing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало извлечения текста из документа
    """
    # Показываем индикатор обработки
    await update.callback_query.message.chat.send_action(ChatAction.TYPING)
    
    file_info = context.user_data['file_info']
    
    # Красивый прогресс-индикатор
    processing_text = (
        f"🔄 **Обработка документа**\n\n"
        f"📄 **Файл:** `{file_info['file_name']}`\n"
        f"📏 **Размер:** {file_info['file_size'] / 1024:.1f} КБ\n"
        f"📝 **Тип:** {'Документ' if file_info['file_type'] == 'document' else 'Изображение (скан)'}\n\n"
        
        "🔍 **Этапы обработки:**\n"
        "▶️ Извлечение текста...\n"
        "⏸️ Анализ содержимого\n"
        "⏸️ Формирование отчета\n\n"
        
        "⏳ *Пожалуйста, подождите...*"
    )
    
    progress_message = await update.callback_query.message.reply_text(
        processing_text,
        parse_mode='Markdown'
    )
    
    # Сохраняем сообщение для обновления прогресса
    context.user_data['progress_message'] = progress_message
    
    try:
        # Извлекаем текст из документа
        extracted_text = await extract_text_from_file(file_info)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            await update.callback_query.message.reply_text(
                "❌ **Ошибка извлечения текста**\n\n"
                "Не удалось извлечь текст из документа. Возможные причины:\n"
                "• Плохое качество скана\n"
                "• Поврежденный файл\n"
                "• Документ не содержит текста\n\n"
                "Попробуйте загрузить другой файл.",
                parse_mode='Markdown'
            )
            return AnalysisStates.DOCUMENT_UPLOAD.value
        
        # Сохраняем извлеченный текст
        context.user_data['extracted_text'] = extracted_text
        
        # Обновляем прогресс
        progress_message = context.user_data.get('progress_message')
        if progress_message:
            updated_progress = (
                f"🔄 **Обработка документа**\n\n"
                f"📄 **Файл:** `{file_info['file_name']}`\n"
                f"📏 **Размер:** {file_info['file_size'] / 1024:.1f} КБ\n"
                f"📝 **Тип:** {'Документ' if file_info['file_type'] == 'document' else 'Изображение (скан)'}\n\n"
                
                "🔍 **Этапы обработки:**\n"
                "✅ Извлечение текста\n"
                "▶️ Анализ содержимого...\n"
                "⏸️ Формирование отчета\n\n"
                
                "⏳ *Анализируем документ...*"
            )
            
            try:
                await progress_message.edit_text(
                    updated_progress,
                    parse_mode='Markdown'
                )
            except Exception:
                pass  # Игнорируем ошибки редактирования
        
        # Показываем краткую статистику извлеченного текста
        words_count = len(extracted_text.split())
        chars_count = len(extracted_text)
        
        # Определяем качество извлечения
        if chars_count > 1000:
            quality_indicator = "🟢 Отличное качество"
        elif chars_count > 300:
            quality_indicator = "🟡 Хорошее качество"
        else:
            quality_indicator = "🟠 Удовлетворительное качество"
        
        stats_message = (
            f"✅ **Текст успешно извлечен**\n\n"
            f"📊 **Статистика извлечения:**\n"
            f"• **Символов:** {chars_count:,}\n"
            f"• **Слов:** {words_count:,}\n"
            f"• **Качество:** {quality_indicator}\n\n"
            "🧠 Переходим к анализу содержимого..."
        )
        
        await update.callback_query.message.reply_text(
            stats_message,
            parse_mode='Markdown'
        )
        
        # Переходим к анализу
        return await start_analysis_processing(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка извлечения текста: {e}")
        await update.callback_query.message.reply_text(
            "❌ **Техническая ошибка**\n\n"
            "Произошла ошибка при обработке документа.\n"
            "Попробуйте:\n"
            "• Загрузить файл еще раз\n"
            "• Использовать другой формат\n"
            "• Обратиться в поддержку\n\n"
            "Для повторной попытки используйте /analyze",
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def start_analysis_processing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало анализа текста через GigaChat
    """
    # Показываем индикатор обработки
    await update.callback_query.message.chat.send_action(ChatAction.TYPING)
    
    analysis_type = context.user_data['analysis_type']
    extracted_text = context.user_data['extracted_text']
    analysis_info = ANALYSIS_TYPES[analysis_type]
    file_info = context.user_data['file_info']
    
    # Обновляем основной прогресс
    progress_message = context.user_data.get('progress_message')
    if progress_message:
        final_progress = (
            f"🔄 **Обработка документа**\n\n"
            f"📄 **Файл:** `{file_info['file_name']}`\n"
            f"📏 **Размер:** {file_info['file_size'] / 1024:.1f} КБ\n"
            f"📝 **Тип:** {'Документ' if file_info['file_type'] == 'document' else 'Изображение (скан)'}\n\n"
            
            "🔍 **Этапы обработки:**\n"
            "✅ Извлечение текста\n"
            "✅ Анализ содержимого\n"
            "▶️ Формирование отчета...\n\n"
            
            "🧠 *Генерируем профессиональный анализ...*"
        )
        
        try:
            await progress_message.edit_text(
                final_progress,
                parse_mode='Markdown'
            )
        except Exception:
            pass
    
    # Детальный статус анализа
    analysis_status = (
        f"🧠 **AI-Анализ документа**\n\n"
        f"{analysis_info['icon']} **{analysis_info['name']}**\n"
        f"📄 **Документ:** `{file_info['file_name']}`\n\n"
        
        "🔍 **Процесс анализа:**\n"
        "▶️ Отправка в GigaChat API...\n"
        "⏸️ Проверка соответствия законодательству\n"
        "⏸️ Выявление проблем и рисков\n"
        "⏸️ Формирование рекомендаций\n\n"
        
        "⏳ *Ожидаемое время: 30-60 секунд*\n"
        "🤖 *Используется профессиональный AI-юрист*"
    )
    
    analysis_message = await update.callback_query.message.reply_text(
        analysis_status,
        parse_mode='Markdown'
    )
    
    # Сохраняем для возможного обновления
    context.user_data['analysis_message'] = analysis_message
    
    try:
        # Получаем имя файла
        file_info = context.user_data['file_info']
        filename = file_info['file_name']
        
        # Анализируем текст через GigaChat
        analysis_result = await analyze_text_with_gigachat(analysis_type, extracted_text, filename)
        
        # Сохраняем результат
        context.user_data['analysis_result'] = analysis_result
        
        # Показываем результат
        return await show_analysis_results(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        await update.callback_query.message.reply_text(
            "❌ **Ошибка анализа**\n\n"
            "Произошла ошибка при анализе документа.\n"
            "Попробуйте:\n"
            "• Повторить анализ через минуту\n"
            "• Выбрать другой тип анализа\n"
            "• Обратиться в поддержку\n\n"
            "Что делаем дальше?",
            parse_mode='Markdown'
        )
        return AnalysisStates.RESULTS_REVIEW.value


async def show_analysis_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показ результатов анализа с улучшенным форматированием
    """
    analysis_result = context.user_data['analysis_result']
    file_info = context.user_data['file_info']
    analysis_type = context.user_data['analysis_type']
    analysis_info = ANALYSIS_TYPES[analysis_type]
    
    # Завершаем прогресс-индикаторы
    progress_message = context.user_data.get('progress_message')
    analysis_message = context.user_data.get('analysis_message')
    
    if progress_message:
        completion_status = (
            f"✅ **Обработка завершена**\n\n"
            f"📄 **Файл:** `{file_info['file_name']}`\n"
            f"📏 **Размер:** {file_info['file_size'] / 1024:.1f} КБ\n"
            f"📝 **Тип:** {'Документ' if file_info['file_type'] == 'document' else 'Изображение (скан)'}\n\n"
            
            "🔍 **Этапы обработки:**\n"
            "✅ Извлечение текста\n"
            "✅ Анализ содержимого\n"
            "✅ Формирование отчета\n\n"
            
            "🎉 *Анализ успешно завершен!*"
        )
        
        try:
            await progress_message.edit_text(
                completion_status,
                parse_mode='Markdown'
            )
        except Exception:
            pass
    
    if analysis_message:
        try:
            await analysis_message.edit_text(
                f"✅ **Анализ завершен**\n\n"
                f"{analysis_info['icon']} **{analysis_info['name']}**\n"
                f"📄 **Документ:** `{file_info['file_name']}`\n\n"
                "🎯 Результат готов к просмотру ниже ⬇️",
                parse_mode='Markdown'
            )
        except Exception:
            pass
    
    # Создаем расширенную клавиатуру для дополнительных действий
    keyboard = [
        [
            InlineKeyboardButton("🔄 Другой тип анализа", callback_data="change_analysis_type"),
            InlineKeyboardButton("📄 Новый документ", callback_data="upload_new_document")
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
            InlineKeyboardButton("❌ Завершить", callback_data="finish_analysis")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем результат с улучшенной разбивкой
    await send_long_message(
        update.callback_query.message.chat,
        analysis_result,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return AnalysisStates.RESULTS_REVIEW.value


async def handle_additional_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик дополнительных действий
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "change_analysis_type":
        # Возврат к выбору типа анализа
        keyboard = []
        for analysis_type, info in ANALYSIS_TYPES.items():
            keyboard.append([InlineKeyboardButton(
                info['name'], 
                callback_data=f"analysis_type_{analysis_type}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_analysis")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "🎯 **Выберите новый тип анализа:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return AnalysisStates.ANALYSIS_TYPE_SELECTION.value
        
    elif query.data == "upload_new_document":
        # Возврат к загрузке документа
        return await analyze_command(update, context)
        
    elif query.data == "finish_analysis":
        # Завершение анализа
        context.user_data.clear()
        await query.message.reply_text(
            "✅ **Анализ завершен**\n\n"
            "Спасибо за использование AI-юриста!\n\n"
            "🔄 Для нового анализа используйте /analyze\n"
            "🏠 Главное меню: /start",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    elif query.data == "main_menu":
        # Возврат в главное меню
        context.user_data.clear()
        from bot.handlers import start_command
        return await start_command(update, context)
    
    return AnalysisStates.RESULTS_REVIEW.value


async def cancel_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена анализа документа и возврат в главное меню
    """
    # Очищаем данные
    context.user_data.clear()
    
    # Определяем откуда пришел запрос
    if update.callback_query:
        await update.callback_query.answer()
        
        # Возвращаем в главное меню
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
        
        await update.callback_query.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Анализ документа отменен.\n"
            "Для нового анализа используйте /analyze"
        )
    
    return ConversationHandler.END


# Вспомогательные функции

async def extract_text_from_file(file_info: Dict[str, Any]) -> str:
    """
    Извлечение текста из файла
    """
    file_extension = file_info['file_extension'].lower()
    file_type = file_info['file_type']
    
    try:
        # Скачиваем файл во временную директорию
        temp_file_path = await download_telegram_file(file_info['file_id'], file_extension)
        
        extracted_text = ""
        
        if file_type == 'document':
            if file_extension in ['.doc', '.docx']:
                extracted_text = await extract_text_from_docx(temp_file_path)
            elif file_extension == '.pdf':
                extracted_text = await extract_text_from_pdf(temp_file_path)
        
        elif file_type == 'image':
            extracted_text = await extract_text_from_image(temp_file_path)
        
        # Удаляем временный файл
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        # Очищаем и нормализуем текст
        cleaned_text = clean_extracted_text(extracted_text)
        
        return cleaned_text
        
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из файла {file_info['file_name']}: {e}")
        raise Exception(f"Не удалось извлечь текст из файла: {str(e)}")


async def analyze_text_with_gigachat(analysis_type: str, text: str, filename: str = "документ") -> str:
    """
    Анализ текста через GigaChat API
    """
    try:
        # Импортируем клиент GigaChat
        from ai_gigachat.client import gigachat_client
        
        # Выполняем анализ через GigaChat API
        logger.info(f"Начинаем анализ документа {filename} типа {analysis_type}")
        
        analysis_result = await gigachat_client.analyze_document(
            document_text=text,
            analysis_type=analysis_type,
            filename=filename
        )
        
        logger.info(f"Анализ документа {filename} успешно завершен")
        return analysis_result
        
    except Exception as e:
        logger.error(f"Ошибка при анализе документа {filename}: {e}")
        
        # Возвращаем резервный ответ при ошибке
        analysis_info = ANALYSIS_TYPES[analysis_type]
        
        return f"""❌ **Ошибка анализа документа**
{analysis_info['icon']} **{analysis_info['name']}**
📄 **Файл:** {filename}

К сожалению, произошла ошибка при анализе документа.

**Возможные причины:**
• Временные проблемы с AI-сервисом
• Документ слишком большой или сложный
• Проблемы с сетевым соединением

**Что можно сделать:**
• Попробуйте повторить анализ через несколько минут
• Убедитесь, что документ содержит читаемый текст
• Обратитесь в поддержку, если проблема повторяется

🔄 Попробуйте снова с командой /analyze"""


async def send_long_message(chat, text: str, **kwargs) -> None:
    """
    Умная отправка длинного сообщения с разбивкой на части по смыслу
    """
    MAX_MESSAGE_LENGTH = 4096
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        await chat.send_message(text, **kwargs)
        return
    
    # Разбиваем текст на смысловые части
    parts = smart_split_message(text, MAX_MESSAGE_LENGTH)
    
    # Отправляем части по очереди
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # Последняя часть - с клавиатурой
            await chat.send_message(part, **kwargs)
        else:
            # Промежуточные части - без клавиатуры и с индикатором продолжения
            kwargs_copy = kwargs.copy()
            kwargs_copy.pop('reply_markup', None)
            
            # Добавляем красивый индикатор продолжения
            continuation_indicator = f"\n\n📄 **Часть {i+1}/{len(parts)}** • *Продолжение следует...*"
            await chat.send_message(part + continuation_indicator, **kwargs_copy)
            
            # Небольшая пауза между сообщениями для лучшего восприятия
            await asyncio.sleep(0.5)


def smart_split_message(text: str, max_length: int) -> List[str]:
    """
    Умная разбивка сообщения по смыслу с сохранением форматирования
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_text = text
    
    while len(current_text) > max_length:
        # Приоритеты для разбивки (от наиболее предпочтительного к наименее)
        split_patterns = [
            '\n\n**',          # Новый раздел с заголовком
            '\n**',            # Заголовок
            '\n\n',            # Двойной перенос строки
            '\n•',             # Список
            '\n-',             # Список с тире
            '\n',              # Обычный перенос строки
            '. ',              # Конец предложения
            ', ',              # Запятая
            ' '                # Пробел
        ]
        
        split_index = -1
        
        # Ищем лучшее место для разбивки
        for pattern in split_patterns:
            # Ищем последнее вхождение паттерна в допустимом диапазоне
            temp_index = current_text.rfind(pattern, 0, max_length - 100)  # Оставляем буфер
            if temp_index > max_length // 2:  # Не разбиваем слишком рано
                split_index = temp_index + len(pattern)
                break
        
        # Если не нашли подходящее место, разбиваем по максимальной длине
        if split_index == -1:
            split_index = max_length
        
        # Добавляем часть
        part = current_text[:split_index].strip()
        if part:
            parts.append(part)
        
        # Переходим к оставшемуся тексту
        current_text = current_text[split_index:].strip()
    
    # Добавляем оставшийся текст
    if current_text:
        parts.append(current_text)
    
    return parts


# Функции для извлечения текста из разных типов файлов

async def download_telegram_file(file_id: str, file_extension: str) -> str:
    """
    Скачивание файла из Telegram во временную директорию
    """
    from telegram import Bot
    from config import TELEGRAM_TOKEN
    
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Получаем информацию о файле
    file = await bot.get_file(file_id)
    
    # Создаем временный файл
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"telegram_file_{file_id}{file_extension}")
    
    # Скачиваем файл
    await file.download_to_drive(temp_file_path)
    
    return temp_file_path


async def extract_text_from_docx(file_path: str) -> str:
    """
    Извлечение текста из DOCX файла
    """
    try:
        # Загружаем документ
        doc = DocxDocument(file_path)
        
        # Извлекаем текст из всех параграфов
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text.strip())
        
        # Извлекаем текст из таблиц
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text.strip())
        
        extracted_text = '\n'.join(text_parts)
        
        if not extracted_text.strip():
            raise Exception("Документ не содержит текста или поврежден")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из DOCX: {e}")
        raise Exception(f"Не удалось обработать DOCX файл: {str(e)}")


async def extract_text_from_pdf(file_path: str) -> str:
    """
    Извлечение текста из PDF файла (с поддержкой OCR для сканов)
    """
    extracted_text = ""
    
    try:
        # Сначала пытаемся извлечь текст напрямую через PyMuPDF (быстрее)
        pdf_document = fitz.open(file_path)
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document.get_page(page_num)
            page_text = page.get_text()
            
            if page_text.strip():
                extracted_text += f"\n--- Страница {page_num + 1} ---\n{page_text}\n"
        
        pdf_document.close()
        
        # Если текста достаточно, возвращаем результат
        if len(extracted_text.strip()) > 50:
            return extracted_text
        
        # Если текста мало, пробуем OCR
        logger.info("Мало текста в PDF, пытаемся OCR...")
        ocr_text = await extract_text_from_pdf_with_ocr(file_path)
        
        return ocr_text if ocr_text else extracted_text
        
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из PDF: {e}")
        
        # В случае ошибки пробуем альтернативный метод через PyPDF2
        try:
            return await extract_text_from_pdf_pypdf2(file_path)
        except Exception as e2:
            logger.error(f"Ошибка альтернативного извлечения из PDF: {e2}")
            raise Exception(f"Не удалось обработать PDF файл: {str(e)}")


async def extract_text_from_pdf_pypdf2(file_path: str) -> str:
    """
    Альтернативное извлечение текста из PDF через PyPDF2
    """
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            text_parts = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text.strip():
                    text_parts.append(f"--- Страница {page_num + 1} ---\n{page_text}")
            
            extracted_text = '\n'.join(text_parts)
            
            if not extracted_text.strip():
                raise Exception("PDF не содержит извлекаемого текста")
            
            return extracted_text
            
    except Exception as e:
        raise Exception(f"Ошибка PyPDF2: {str(e)}")


async def extract_text_from_pdf_with_ocr(file_path: str) -> str:
    """
    Извлечение текста из PDF с помощью OCR (для сканированных документов)
    """
    try:
        # Проверяем доступность Tesseract
        if not is_tesseract_available():
            raise Exception("OCR недоступен: требуется установка Tesseract OCR")
        
        # Конвертируем PDF в изображения
        from pdf2image import convert_from_path
        
        # Конвертируем страницы PDF в изображения
        images = convert_from_path(file_path, dpi=300, fmt='jpeg')
        
        text_parts = []
        for i, image in enumerate(images):
            # Применяем OCR к каждой странице
            page_text = pytesseract.image_to_string(image, lang='rus+eng')
            
            if page_text.strip():
                text_parts.append(f"--- Страница {i + 1} ---\n{page_text}")
        
        extracted_text = '\n'.join(text_parts)
        
        if not extracted_text.strip():
            raise Exception("OCR не смог распознать текст в PDF")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Ошибка OCR для PDF: {e}")
        raise Exception(f"Не удалось распознать текст в сканированном PDF: {str(e)}")


async def extract_text_from_image(file_path: str) -> str:
    """
    Извлечение текста из изображения с помощью OCR
    """
    try:
        # Проверяем доступность Tesseract
        if not is_tesseract_available():
            raise Exception("OCR недоступен: требуется установка Tesseract OCR.\n"
                          "Для Windows: скачайте с https://github.com/UB-Mannheim/tesseract/wiki\n"
                          "Для анализа изображений необходимо установить Tesseract OCR в системе.")
        
        # Открываем изображение
        image = Image.open(file_path)
        
        # Применяем OCR
        extracted_text = pytesseract.image_to_string(image, lang='rus+eng')
        
        if not extracted_text.strip():
            raise Exception("OCR не смог распознать текст на изображении")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Ошибка OCR для изображения: {e}")
        raise Exception(f"Не удалось распознать текст на изображении: {str(e)}")


def is_tesseract_available() -> bool:
    """
    Проверка доступности Tesseract OCR
    """
    try:
        import subprocess
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def clean_extracted_text(text: str) -> str:
    """
    Очистка и нормализация извлеченного текста
    """
    if not text:
        return ""
    
    # Заменяем множественные пробелы на одинарные (но сохраняем переносы строк)
    cleaned = re.sub(r'[ \t]+', ' ', text)
    
    # Удаляем повторяющиеся переносы строк (больше 2 подряд)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    
    # Убираем пробелы в начале и конце строк
    lines = [line.strip() for line in cleaned.split('\n')]
    cleaned = '\n'.join(lines)
    
    # Убираем пробелы в начале и конце всего текста
    cleaned = cleaned.strip()
    
    # Проверяем минимальную длину
    if len(cleaned) < 10:
        raise Exception("Извлеченный текст слишком короткий")
    
    return cleaned 