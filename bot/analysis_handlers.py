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
    'document_summary': {
        'name': '📋 Краткое описание',
        'description': 'Краткое описание содержания и назначения документа',
        'icon': '📋'
    },
    'law_compliance': {
        'name': '⚖️ Проверка соответствия закону',
        'description': 'Анализ соответствия документа действующему законодательству РФ',
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
        
        # Если это изображение, обрабатываем как изображение
        if file_extension in SUPPORTED_EXTENSIONS['image']:
            file_type = 'image'
        elif file_extension in SUPPORTED_EXTENSIONS['document']:
            file_type = 'document'
        else:
            await update.message.reply_text(
                f"❌ **Неподдерживаемый формат**\n\n"
                f"Файл: `{file_name}`\n"
                f"Формат: `{file_extension}`\n\n"
                "Поддерживаемые форматы:\n"
                "• **Документы:** DOC, DOCX, PDF\n"
                "• **Изображения:** JPG, PNG, BMP, TIFF\n\n"
                "Пожалуйста, загрузите файл в поддерживаемом формате.",
                parse_mode='Markdown'
            )
            return AnalysisStates.DOCUMENT_UPLOAD.value
        
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
    
    # Показываем индикатор обработки
    processing_message = await update.message.reply_text(
        "🔄 **Обрабатываю документ...**\n\n"
        "📥 Загружаю файл...",
        parse_mode='Markdown'
    )
    
    try:
        # Обновляем статус
        await processing_message.edit_text(
            "🔄 **Обрабатываю документ...**\n\n"
            f"📄 {'🖼️ Сканирую изображение...' if file_type == 'image' else '📝 Извлекаю текст из файла...'}\n"
            "⏳ *Это может занять несколько секунд*",
            parse_mode='Markdown'
        )
        
        # Извлекаем текст из файла
        extracted_text = await extract_text_from_file(context.user_data['file_info'])
        
        # Для изображений (OCR) проверяем менее строго
        min_length = 3 if file_type == 'image' else 10
        
        if not extracted_text or len(extracted_text.strip()) < min_length:
            # Если это изображение и OCR вернул предупреждение, все равно продолжаем
            if file_type == 'image' and extracted_text and "OCR распознал очень мало текста" in extracted_text:
                pass  # Продолжаем с предупреждением
            else:
                # Создаем клавиатуру с навигацией для ошибки
                error_keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="retry_upload")],
                    [InlineKeyboardButton("🔙 Назад к выбору файла", callback_data="back_to_upload")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]
                
                await processing_message.edit_text(
                    "❌ **Ошибка обработки файла**\n\n"
                    "Не удалось извлечь текст из документа.\n\n"
                    "**Возможные причины:**\n"
                    "• Плохое качество скана\n"
                    "• Поврежденный файл\n"
                    "• Документ не содержит текста\n\n"
                    "**Что можно сделать:**\n"
                    "• Попробовать загрузить файл заново\n"
                    "• Использовать изображение лучшего качества\n"
                    "• Попробовать другой формат файла",
                    reply_markup=InlineKeyboardMarkup(error_keyboard),
                    parse_mode='Markdown'
                )
                return AnalysisStates.DOCUMENT_UPLOAD.value
        
        # Сохраняем извлеченный текст
        context.user_data['document_text'] = extracted_text
        
        # Финальное обновление с результатом
        file_icon = "🖼️" if file_type == 'image' else "📄"
        success_text = "✅ **Документ обработан успешно!**\n\n"
        
        if file_type == 'image':
            success_text += f"{file_icon} **Изображение:** {file_name}\n"
            success_text += f"📊 **Размер:** {file_size / 1024 / 1024:.1f} МБ\n"
            success_text += f"🔤 **Текст распознан:** {len(extracted_text)} символов\n"
            if "OCR распознал очень мало текста" in extracted_text:
                success_text += "\n⚠️ *Распознано мало текста, но анализ возможен*"
        else:
            success_text += f"{file_icon} **Файл:** {file_name}\n"
            success_text += f"📊 **Размер:** {file_size / 1024 / 1024:.1f} МБ\n"
            success_text += f"📝 **Текст извлечен:** {len(extracted_text)} символов"
        
        await processing_message.edit_text(
            success_text,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        # Создаем клавиатуру с навигацией для критической ошибки
        error_keyboard = [
            [InlineKeyboardButton("🔄 Попробовать еще раз", callback_data="retry_upload")],
            [InlineKeyboardButton("🔙 Назад к выбору файла", callback_data="back_to_upload")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        await processing_message.edit_text(
            "❌ **Критическая ошибка обработки**\n\n"
            "Произошла непредвиденная ошибка при обработке файла.\n\n"
            "**Попробуйте:**\n"
            "• Загрузить файл заново\n"
            "• Использовать другой формат\n"
            "• Обратиться в поддержку если проблема повторяется",
            reply_markup=InlineKeyboardMarkup(error_keyboard),
            parse_mode='Markdown'
        )
        return AnalysisStates.DOCUMENT_UPLOAD.value
    
    # Предлагаем выбрать тип анализа
    keyboard = create_analysis_keyboard()
    
    await update.message.reply_text(
        f"📄 **Документ получен:** {file_name}\n\n"
        f"📊 **Размер:** {file_size / 1024 / 1024:.1f} МБ\n"
        f"📝 **Текст извлечен:** {len(extracted_text)} символов\n\n"
        "**Выберите тип анализа:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    return AnalysisStates.ANALYSIS_TYPE_SELECTION.value


async def handle_analysis_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора типа анализа
    """
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("analysis_type_"):
        # Выбор типа анализа
        analysis_type = query.data.replace("analysis_type_", "")
        
        if analysis_type not in ANALYSIS_TYPES:
            await query.answer("❌ Неизвестный тип анализа")
            return
        
        # Сохраняем выбранный тип анализа
        context.user_data['analysis_type'] = analysis_type
        
        # Если это краткое описание, сразу запускаем анализ
        if analysis_type == 'document_summary':
            # НЕ УДАЛЯЕМ предыдущее сообщение! Добавляем новое
            progress_msg = await query.message.reply_text("⏳ Создаю краткое описание документа...")
            
            # Получаем текст документа
            document_text = context.user_data.get('document_text', '')
            if not document_text:
                await query.message.reply_text("❌ Текст документа не найден. Попробуйте загрузить файл заново.")
                return
            
            try:
                # Выполняем анализ
                analysis_result = await gigachat_client.analyze_document(
                    document_text, 
                    analysis_type
                )
                
                # Обновляем прогресс сообщение
                await progress_msg.edit_text("✅ Краткое описание готово!")
                
                # Устанавливаем флаг что краткое описание выполнено
                context.user_data['summary_done'] = True
                
                # Создаем клавиатуру с остальными типами анализа
                keyboard = create_other_analysis_keyboard()
                
                await query.message.reply_text(
                    analysis_result,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                return
            except Exception as e:
                await query.message.reply_text(
                    "❌ **Ошибка анализа**\n\n"
                    "Произошла ошибка при создании краткого описания.\n"
                    "Попробуйте повторить попытку.",
                    parse_mode='Markdown'
                )
                return
        
        # Для остальных типов анализа
        analysis_info = ANALYSIS_TYPES[analysis_type]
        
        # Если краткое описание уже было сделано, сразу запускаем анализ
        if context.user_data.get('summary_done'):
            # НЕ УДАЛЯЕМ предыдущие сообщения! Добавляем новое
            progress_msg = await query.message.reply_text("⏳ Выполняю анализ документа...")
            
            # Получаем текст документа
            document_text = context.user_data.get('document_text') or context.user_data.get('extracted_text', '')
            if not document_text:
                await query.message.reply_text("❌ Текст документа не найден. Попробуйте загрузить файл заново.")
                return
            
            try:
                # Выполняем анализ
                analysis_result = await gigachat_client.analyze_document(
                    document_text, 
                    analysis_type
                )
                
                # Обновляем прогресс сообщение
                await progress_msg.edit_text("✅ Анализ завершен!")
                
                # Создаем клавиатуру для завершения или выбора другого анализа
                keyboard = [
                    [InlineKeyboardButton("📊 Другой тип анализа", callback_data="back_to_analysis_types")],
                    [InlineKeyboardButton("✅ Завершить", callback_data="finish_analysis")]
                ]
                
                await query.message.reply_text(
                    analysis_result,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                return
            except Exception as e:
                await query.message.reply_text(
                    "❌ **Ошибка анализа**\n\n"
                    "Произошла ошибка при анализе документа.\n"
                    "Попробуйте повторить попытку или выбрать другой тип анализа.",
                    parse_mode='Markdown'
                )
                return
        
        # Для первичного выбора (без краткого описания) показываем подтверждение
        keyboard = [
            [InlineKeyboardButton("✅ Начать анализ", callback_data="start_analysis")],
            [InlineKeyboardButton("🔙 Выбрать другой тип", callback_data="back_to_analysis_types")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_analysis")]
        ]
        
        # НЕ УДАЛЯЕМ предыдущие сообщения! Добавляем новое
        await query.message.reply_text(
            f"**{analysis_info['icon']} {analysis_info['name']}**\n\n"
            f"{analysis_info['description']}\n\n"
            "Начать анализ?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    elif query.data == "start_analysis":
        # Начать анализ после подтверждения
        progress_msg = await query.message.reply_text("⏳ Выполняю анализ документа...")
        
        # Получаем данные из контекста
        analysis_type = context.user_data.get('analysis_type')
        # Пробуем получить текст из разных переменных (для совместимости)
        document_text = context.user_data.get('document_text') or context.user_data.get('extracted_text', '')
        
        if not analysis_type or not document_text:
            await query.message.reply_text("❌ Данные для анализа не найдены. Попробуйте загрузить файл заново.")
            return
        
        try:
            # Выполняем анализ
            analysis_result = await gigachat_client.analyze_document(
                document_text, 
                analysis_type
            )
            
            # Обновляем прогресс сообщение
            await progress_msg.edit_text("✅ Анализ завершен!")
            
            # Создаем клавиатуру для завершения или выбора другого анализа
            keyboard = [
                [InlineKeyboardButton("📊 Другой тип анализа", callback_data="back_to_analysis_types")],
                [InlineKeyboardButton("✅ Завершить", callback_data="finish_analysis")]
            ]
            
            await query.message.reply_text(
                analysis_result,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.message.reply_text(
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
    
    elif query.data == "back_to_analysis_types":
        # Вернуться к выбору типа анализа
        # Проверяем, было ли уже выполнено краткое описание
        if context.user_data.get('summary_done'):
            # Если краткое описание уже было, показываем остальные типы
            keyboard = create_other_analysis_keyboard()
        else:
            # Если краткого описания не было, показываем полную клавиатуру
            keyboard = create_analysis_keyboard()
        
        # НЕ УДАЛЯЕМ предыдущие сообщения! Добавляем новое
        await query.message.reply_text(
            "**Выберите тип анализа:**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif query.data == "change_analysis_type":
        # ДОБАВЛЯЮ ОТСУТСТВУЮЩИЙ ОБРАБОТЧИК!
        # Проверяем, было ли уже выполнено краткое описание
        if context.user_data.get('summary_done'):
            keyboard = create_other_analysis_keyboard()
        else:
            keyboard = create_analysis_keyboard()
        
        await query.message.reply_text(
            "🎯 **Выберите новый тип анализа:**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif query.data == "cancel_analysis":
        # ДОБАВЛЯЮ ОТСУТСТВУЮЩИЙ ОБРАБОТЧИК!
        return await cancel_analysis(update, context)
    
    elif query.data == "back_to_menu":
        # ДОБАВЛЯЮ ОТСУТСТВУЮЩИЙ ОБРАБОТЧИК!
        # Возврат в главное меню через cancel_analysis
        return await cancel_analysis(update, context)
    
    elif query.data == "retry_upload":
        # Повторная попытка загрузки файла
        await query.message.reply_text(
            "🔄 **Повторная загрузка**\n\n"
            "Пожалуйста, загрузите документ заново:\n\n"
            "📋 **Поддерживаемые форматы:**\n"
            "• **Документы:** DOC, DOCX, PDF\n"
            "• **Изображения:** JPG, PNG (сканы)\n"
            "• **Максимальный размер:** 10 МБ",
            parse_mode='Markdown'
        )
        return AnalysisStates.DOCUMENT_UPLOAD.value
    
    elif query.data == "back_to_upload":
        # Возврат к началу загрузки документа
        return await analyze_command(update, context)
    
    # КРИТИЧЕСКИ ВАЖНО: возвращаем состояние для ConversationHandler!
    return AnalysisStates.ANALYSIS_TYPE_SELECTION.value


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
            "• Обратиться в поддержку",
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
        
        # Создаем клавиатуру для выбора дальнейших действий
        keyboard = [
            [InlineKeyboardButton("📊 Новый анализ", callback_data="start_analyze")],
            [InlineKeyboardButton("💬 Консультация", callback_data="menu_consult")],
            [InlineKeyboardButton("📄 Создать документ", callback_data="menu_create")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "✅ **Анализ завершен**\n\n"
            "Спасибо за использование AI-юриста!\n\n"
            "Выберите дальнейшие действия:",
            reply_markup=reply_markup,
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
            "Используйте кнопки ниже для выбора действий."
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

🔄 Используйте кнопки ниже для дальнейших действий"""


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
        logger.info(f"Начинаем OCR обработку изображения: {file_path}")
        
        # Проверяем доступность Tesseract
        if not is_tesseract_available():
            logger.error("Tesseract OCR недоступен")
            raise Exception("OCR недоступен: требуется установка Tesseract OCR.\n"
                          "Для анализа изображений необходимо установить Tesseract OCR в системе.")
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            logger.error(f"Файл изображения не найден: {file_path}")
            raise Exception("Файл изображения не найден")
        
        logger.info(f"Размер файла: {os.path.getsize(file_path)} байт")
        
        # Открываем изображение
        image = Image.open(file_path)
        logger.info(f"Изображение открыто: {image.size}, режим: {image.mode}")
        
        # Конвертируем в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
            logger.info("Изображение конвертировано в RGB")
        
        # Улучшаем качество изображения для лучшего OCR
        # Увеличиваем размер если изображение маленькое
        width, height = image.size
        if width < 1000 or height < 1000:
            scale_factor = max(1000 / width, 1000 / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Изображение увеличено до {new_width}x{new_height}")
        
        # Применяем OCR с разными настройками
        logger.info("Применяем OCR...")
        
        # Пробуем несколько конфигураций OCR
        ocr_configs = [
            '--psm 3',  # Полностью автоматическая сегментация страницы (по умолчанию)
            '--psm 6',  # Единый блок текста
            '--psm 4',  # Одна колонка текста различных размеров
        ]
        
        extracted_text = ""
        for config in ocr_configs:
            try:
                text = pytesseract.image_to_string(image, lang='rus+eng', config=config)
                if text and len(text.strip()) > len(extracted_text.strip()):
                    extracted_text = text
                    logger.info(f"OCR успешен с конфигурацией {config}, длина текста: {len(text.strip())}")
            except Exception as e:
                logger.warning(f"OCR с конфигурацией {config} не удался: {e}")
                continue
        
        if not extracted_text or len(extracted_text.strip()) < 5:
            logger.warning(f"OCR вернул мало текста: '{extracted_text[:100]}...'")
            
            # Попробуем только английский язык
            try:
                text_eng = pytesseract.image_to_string(image, lang='eng')
                if len(text_eng.strip()) > len(extracted_text.strip()):
                    extracted_text = text_eng
                    logger.info(f"OCR с английским языком дал лучший результат: {len(text_eng.strip())}")
            except Exception as e:
                logger.warning(f"OCR только с английским не удался: {e}")
            
            # Если все еще мало текста, возвращаем что есть с предупреждением
            if len(extracted_text.strip()) < 5:
                return f"⚠️ OCR распознал очень мало текста.\n\nВозможные причины:\n• Плохое качество изображения\n• Неразборчивый текст\n• Необычный шрифт\n\nРаспознанный текст:\n{extracted_text.strip()}"
        
        logger.info(f"OCR завершен успешно, итоговая длина: {len(extracted_text.strip())}")
        return extracted_text
        
    except Exception as e:
        logger.error(f"Критическая ошибка OCR для изображения {file_path}: {e}")
        return f"❌ Ошибка OCR: {str(e)}\n\nПопробуйте:\n• Загрузить изображение лучшего качества\n• Использовать более контрастное изображение\n• Убедиться что текст четко виден"


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
    
    # Для OCR результатов не требуем минимальную длину
    # Возвращаем текст как есть, даже если он короткий
    return cleaned

def create_analysis_keyboard():
    """Создает клавиатуру для выбора типа анализа"""
    keyboard = []
    
    # Добавляем кнопку "Краткое описание" первой
    keyboard.append([InlineKeyboardButton(
        ANALYSIS_TYPES['document_summary']['name'], 
        callback_data="analysis_type_document_summary"
    )])
    
    # Добавляем остальные типы анализа
    for analysis_type, info in ANALYSIS_TYPES.items():
        if analysis_type != 'document_summary':  # Пропускаем, так как уже добавили
            keyboard.append([InlineKeyboardButton(
                info['name'], 
                callback_data=f"analysis_type_{analysis_type}"
            )])
    
    # Кнопки управления
    keyboard.extend([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(keyboard) 

def create_other_analysis_keyboard():
    """Создает клавиатуру с остальными типами анализа (без краткого описания)"""
    keyboard = []
    
    # Добавляем все типы анализа кроме document_summary
    for analysis_type, info in ANALYSIS_TYPES.items():
        if analysis_type != 'document_summary':
            keyboard.append([InlineKeyboardButton(
                info['name'], 
                callback_data=f"analysis_type_{analysis_type}"
            )])
    
    # Кнопки управления
    keyboard.extend([
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(keyboard) 