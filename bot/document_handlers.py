#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для создания юридических документов
"""

import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler  # type: ignore
from telegram.constants import ChatAction  # type: ignore

from ai_gigachat.client import gigachat_client

logger = logging.getLogger(__name__)


class DocumentStates(Enum):
    """Состояния диалога создания документов"""
    DOCUMENT_TYPE_SELECTION = 0
    DOCUMENT_SUBTYPE_SELECTION = 1
    DATA_COLLECTION = 2
    DOCUMENT_GENERATION = 3
    DOCUMENT_REVIEW = 4
    DOCUMENT_EDITING = 5
    DOCUMENT_FINALIZATION = 6


# Типы документов и их подтипы
DOCUMENT_TYPES = {
    "contract": {
        "name": "📄 Договор",
        "subtypes": {
            "rent": "Аренды",
            "sale": "Купли-продажи", 
            "service": "Оказания услуг",
            "work": "Выполнения работ",
            "employment": "Трудовой",
            "loan": "Займа"
        }
    },
    "lawsuit": {
        "name": "⚖️ Исковое заявление",
        "subtypes": {
            "property": "Имущественный спор",
            "family": "Семейный спор",
            "labor": "Трудовой спор",
            "compensation": "Возмещение ущерба",
            "debt": "Взыскание долга"
        }
    },
    "claim": {
        "name": "📧 Досудебная претензия",
        "subtypes": {
            "payment": "О взыскании долга",
            "quality": "О некачественном товаре/услуге",
            "contract": "О нарушении договора",
            "refund": "О возврате денежных средств"
        }
    },
    "agreement": {
        "name": "🤝 Соглашение",
        "subtypes": {
            "settlement": "Мировое соглашение",
            "alimony": "Об алиментах",
            "property": "О разделе имущества",
            "cooperation": "О сотрудничестве"
        }
    },
    "power_of_attorney": {
        "name": "📋 Доверенность",
        "subtypes": {
            "general": "Генеральная",
            "property": "На недвижимость",
            "vehicle": "На автомобиль",
            "bank": "В банк",
            "court": "В суд"
        }
    },
    "application": {
        "name": "📝 Заявление",
        "subtypes": {
            "court": "В суд",
            "police": "В полицию",
            "administration": "В администрацию",
            "employer": "Работодателю"
        }
    },
    "protocol": {
        "name": "📊 Протокол",
        "subtypes": {
            "meeting": "Собрания",
            "inspection": "Осмотра",
            "violation": "Нарушения",
            "handover": "Передачи"
        }
    },
    "act": {
        "name": "📑 Акт",
        "subtypes": {
            "acceptance": "Приема-передачи",
            "inspection": "Осмотра",
            "completion": "Выполненных работ",
            "damage": "О повреждении"
        }
    }
}


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /create
    Запускает процесс создания юридического документа
    """
    user = update.effective_user
    user_name = user.first_name if user.first_name else "пользователь"
    
    # Очищаем предыдущие данные документа
    context.user_data.pop('document_data', None)
    context.user_data.pop('document_type', None)
    context.user_data.pop('document_subtype', None)
    context.user_data.pop('generated_document', None)
    
    welcome_text = (
        f"📄 Привет, {user_name}!\n\n"
        "🎯 Я помогу вам создать юридический документ.\n\n"
        "💡 **Доступные типы документов:**\n"
        "• Договоры различных типов\n"
        "• Исковые заявления\n"
        "• Досудебные претензии\n"
        "• Соглашения и доверенности\n"
        "• Заявления и протоколы\n\n"
        "Выберите тип документа:"
    )
    
    # Создаем клавиатуру с типами документов
    keyboard = []
    for doc_type, info in DOCUMENT_TYPES.items():
        keyboard.append([InlineKeyboardButton(info["name"], callback_data=f"doctype_{doc_type}")])
    
    # Добавляем кнопку главного меню
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
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
        # Вызвано из обычного сообщения (команда /create)
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )
    
    return DocumentStates.DOCUMENT_TYPE_SELECTION.value


async def document_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора типа документа
    """
    query = update.callback_query
    await query.answer()
    
    doc_type = query.data.replace("doctype_", "")
    context.user_data['document_type'] = doc_type
    
    doc_info = DOCUMENT_TYPES[doc_type]
    
    subtype_text = (
        f"📄 **Выбран тип: {doc_info['name']}**\n\n"
        "Теперь выберите подтип документа:"
    )
    
    # Создаем клавиатуру с подтипами
    keyboard = []
    for subtype_key, subtype_name in doc_info["subtypes"].items():
        callback_data = f"docsubtype_{subtype_key}"
        keyboard.append([InlineKeyboardButton(f"📋 {subtype_name}", callback_data=callback_data)])
    
    # Кнопки навигации
    keyboard.extend([
        [InlineKeyboardButton("⬅️ Назад к типам", callback_data="back_to_types")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        subtype_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return DocumentStates.DOCUMENT_SUBTYPE_SELECTION.value


async def document_subtype_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик выбора подтипа документа
    Начинает сбор данных
    """
    query = update.callback_query
    await query.answer()
    
    subtype = query.data.replace("docsubtype_", "")
    context.user_data['document_subtype'] = subtype
    
    # Инициализируем данные документа
    context.user_data['document_data'] = {}
    context.user_data['current_question'] = 0
    
    doc_type = context.user_data['document_type']
    doc_info = DOCUMENT_TYPES[doc_type]
    subtype_name = doc_info["subtypes"][subtype]
    
    confirmation_text = (
        f"✅ **Выбран документ: {doc_info['name']} - {subtype_name}**\n\n"
        "📝 Теперь я задам вам несколько вопросов для заполнения документа.\n"
        "Отвечайте максимально подробно для качественного результата.\n\n"
        "Готовы начать?"
    )
    
    keyboard = [
        [InlineKeyboardButton("▶️ Начать заполнение", callback_data="start_data_collection")],
        [InlineKeyboardButton("⬅️ Назад к подтипам", callback_data="back_to_subtypes")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        confirmation_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return DocumentStates.DATA_COLLECTION.value


async def start_data_collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало сбора данных для документа
    """
    query = update.callback_query
    await query.answer()
    
    # Переходим к первому вопросу
    return await ask_next_question(update, context, is_callback=True)


async def ask_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """
    Задает следующий вопрос для сбора данных
    """
    doc_type = context.user_data['document_type']
    doc_subtype = context.user_data['document_subtype']
    current_question = context.user_data.get('current_question', 0)
    
    # Получаем список вопросов для данного типа документа
    questions = get_questions_for_document(doc_type, doc_subtype)
    
    if current_question >= len(questions):
        # Все вопросы заданы, переходим к генерации
        return await start_document_generation(update, context, is_callback)
    
    question_data = questions[current_question]
    question_text = (
        f"❓ **Вопрос {current_question + 1} из {len(questions)}**\n\n"
        f"{question_data['question']}\n\n"
        f"💡 *{question_data['hint']}*"
    )
    
    keyboard = []
    
    # Если есть варианты ответов, добавляем их как кнопки
    if 'options' in question_data:
        for option in question_data['options']:
            keyboard.append([InlineKeyboardButton(option, callback_data=f"answer_{option}")])
        keyboard.append([InlineKeyboardButton("✍️ Ввести свой вариант", callback_data="custom_answer")])
    
    # Кнопки навигации
    if current_question > 0:
        keyboard.append([InlineKeyboardButton("⬅️ Предыдущий вопрос", callback_data="prev_question")])
    
    keyboard.extend([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await update.callback_query.message.reply_text(
            question_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            question_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return DocumentStates.DATA_COLLECTION.value


def get_questions_for_document(doc_type: str, doc_subtype: str) -> List[Dict[str, Any]]:
    """
    Возвращает список вопросов для конкретного типа документа
    """
    # Базовые вопросы для разных типов документов
    questions_map = {
        "contract": {
            "rent": [
                {
                    "key": "landlord_name",
                    "question": "Укажите ФИО арендодателя (полностью)",
                    "hint": "Например: Иванов Иван Иванович"
                },
                {
                    "key": "tenant_name", 
                    "question": "Укажите ФИО арендатора (полностью)",
                    "hint": "Например: Петров Петр Петрович"
                },
                {
                    "key": "property_address",
                    "question": "Укажите полный адрес арендуемого имущества",
                    "hint": "Включите город, улицу, дом, квартиру"
                },
                {
                    "key": "property_type",
                    "question": "Что сдается в аренду?",
                    "hint": "Выберите тип имущества",
                    "options": ["Квартира", "Комната", "Дом", "Офис", "Торговое помещение", "Склад"]
                },
                {
                    "key": "rent_amount",
                    "question": "Укажите размер арендной платы (в рублях)",
                    "hint": "Например: 50000"
                },
                {
                    "key": "rent_period",
                    "question": "Как часто вносится арендная плата?",
                    "hint": "Выберите периодичность",
                    "options": ["Ежемесячно", "Ежеквартально", "Раз в полгода", "Ежегодно"]
                },
                {
                    "key": "contract_duration",
                    "question": "На какой срок заключается договор?",
                    "hint": "Например: 1 год, 6 месяцев, 2 года"
                }
            ],
            "sale": [
                {
                    "key": "seller_name",
                    "question": "Укажите ФИО продавца (полностью)",
                    "hint": "Например: Иванов Иван Иванович"
                },
                {
                    "key": "buyer_name",
                    "question": "Укажите ФИО покупателя (полностью)", 
                    "hint": "Например: Петров Петр Петрович"
                },
                {
                    "key": "item_description",
                    "question": "Что продается? Опишите предмет сделки",
                    "hint": "Укажите наименование, характеристики, состояние"
                },
                {
                    "key": "sale_price",
                    "question": "Укажите цену продажи (в рублях)",
                    "hint": "Например: 1500000"
                },
                {
                    "key": "payment_method",
                    "question": "Как будет происходить оплата?",
                    "hint": "Выберите способ расчета",
                    "options": ["Наличные", "Безналичный расчет", "Рассрочка", "Ипотека"]
                }
            ]
        },
        "lawsuit": {
            "debt": [
                {
                    "key": "plaintiff_name",
                    "question": "Укажите ФИО истца (полностью)",
                    "hint": "Ваши данные или данные представляемого лица"
                },
                {
                    "key": "defendant_name", 
                    "question": "Укажите ФИО ответчика (полностью)",
                    "hint": "Лицо, с которого взыскивается долг"
                },
                {
                    "key": "debt_amount",
                    "question": "Укажите размер долга (в рублях)",
                    "hint": "Основная сумма без процентов и штрафов"
                },
                {
                    "key": "debt_basis",
                    "question": "На основании чего возник долг?",
                    "hint": "Договор, расписка, решение суда и т.д."
                },
                {
                    "key": "debt_date",
                    "question": "Когда должен был быть погашен долг?",
                    "hint": "Дата, когда ответчик должен был вернуть деньги"
                }
            ]
        },
        "claim": {
            "payment": [
                {
                    "key": "creditor_name",
                    "question": "Укажите ваше ФИО (кредитор)",
                    "hint": "Тот, кому должны деньги"
                },
                {
                    "key": "debtor_name",
                    "question": "Укажите ФИО должника",
                    "hint": "Тот, кто должен деньги"
                },
                {
                    "key": "debt_amount",
                    "question": "Размер задолженности (в рублях)",
                    "hint": "Сумма основного долга"
                },
                {
                    "key": "debt_reason",
                    "question": "По какому основанию возникла задолженность?",
                    "hint": "Договор, услуга, товар и т.д."
                }
            ]
        }
    }
    
    # Возвращаем вопросы для конкретного типа или базовые вопросы
    if doc_type in questions_map and doc_subtype in questions_map[doc_type]:
        return questions_map[doc_type][doc_subtype]
    
    # Базовые вопросы, если специфичных нет
    return [
        {
            "key": "party1_name",
            "question": "Укажите ФИО первой стороны",
            "hint": "Полные данные первой стороны документа"
        },
        {
            "key": "party2_name", 
            "question": "Укажите ФИО второй стороны",
            "hint": "Полные данные второй стороны документа"
        },
        {
            "key": "subject",
            "question": "Опишите предмет/суть документа",
            "hint": "О чем этот документ, что регулирует"
        }
    ]


# Функции навигации и вспомогательные обработчики
async def back_to_types(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору типа документа"""
    query = update.callback_query
    await query.answer()
    
    # Имитируем команду /create
    update.message = query.message
    return await create_command(update, context)


async def back_to_subtypes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат к выбору подтипа документа"""
    query = update.callback_query
    await query.answer()
    
    doc_type = context.user_data['document_type']
    query.data = f"doctype_{doc_type}"
    
    return await document_type_selected(update, context)


async def cancel_document_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена создания документа"""
    # Очищаем данные
    context.user_data.pop('document_data', None)
    context.user_data.pop('document_type', None)
    context.user_data.pop('document_subtype', None)
    context.user_data.pop('generated_document', None)
    
    await update.message.reply_text(
        "❌ Создание документа отменено.\n"
        "Для создания нового документа используйте /create"
    )
    return ConversationHandler.END


async def process_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка ответа пользователя на вопрос
    """
    if update.callback_query:
        # Ответ через кнопку
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("answer_"):
            # Выбран готовый вариант ответа
            answer = query.data.replace("answer_", "")
            return await save_answer_and_continue(update, context, answer, is_callback=True)
        elif query.data == "custom_answer":
            # Пользователь хочет ввести свой ответ
            await query.message.reply_text(
                "✍️ Введите ваш ответ:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_custom")]
                ])
            )
            return DocumentStates.DATA_COLLECTION.value
        elif query.data == "prev_question":
            # Переход к предыдущему вопросу
            context.user_data['current_question'] = max(0, context.user_data.get('current_question', 0) - 1)
            return await ask_next_question(update, context, is_callback=True)
    else:
        # Текстовый ответ
        answer = update.message.text
        return await save_answer_and_continue(update, context, answer)


async def save_answer_and_continue(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str, is_callback: bool = False) -> int:
    """
    Сохраняет ответ и переходит к следующему вопросу
    """
    doc_type = context.user_data['document_type']
    doc_subtype = context.user_data['document_subtype']
    current_question = context.user_data.get('current_question', 0)
    
    # Получаем вопросы для сохранения ключа
    questions = get_questions_for_document(doc_type, doc_subtype)
    
    if current_question < len(questions):
        question_key = questions[current_question]['key']
        context.user_data['document_data'][question_key] = answer
        
        # Подтверждение сохранения ответа
        confirmation_text = f"✅ Ответ сохранен: *{answer}*"
        
        if is_callback:
            await update.callback_query.message.reply_text(
                confirmation_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                confirmation_text,
                parse_mode='Markdown'
            )
    
    # Переходим к следующему вопросу
    context.user_data['current_question'] = current_question + 1
    return await ask_next_question(update, context, is_callback=is_callback)


async def start_document_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """
    Начинает процесс генерации документа
    """
    doc_type = context.user_data['document_type']
    doc_subtype = context.user_data['document_subtype']
    document_data = context.user_data['document_data']
    
    doc_info = DOCUMENT_TYPES[doc_type]
    subtype_name = doc_info["subtypes"][doc_subtype]
    
    generation_text = (
        f"🎯 **Генерация документа: {doc_info['name']} - {subtype_name}**\n\n"
        "⏳ Собранная информация обрабатывается...\n"
        "📝 Создаю профессиональный юридический документ...\n\n"
        "*Это может занять несколько секунд*"
    )
    
    if is_callback:
        await update.callback_query.message.reply_text(
            generation_text,
            parse_mode='Markdown'
        )
        # Показываем индикатор печати
        await update.callback_query.message.chat.send_action(ChatAction.TYPING)
    else:
        await update.message.reply_text(
            generation_text,
            parse_mode='Markdown'
        )
        await update.message.chat.send_action(ChatAction.TYPING)
    
    try:
        # Генерируем документ через GigaChat
        generated_document = await generate_document_with_gigachat(doc_type, doc_subtype, document_data)
        context.user_data['generated_document'] = generated_document
        
        # Показываем результат
        return await show_generated_document(update, context, is_callback)
        
    except Exception as e:
        logger.error(f"Ошибка генерации документа: {e}")
        error_text = (
            "❌ **Ошибка генерации документа**\n\n"
            "Произошла техническая ошибка. Попробуйте:\n"
            "• Проверить правильность введенных данных\n"
            "• Повторить попытку через минуту\n"
            "• Обратиться в поддержку\n\n"
            "Что делаем дальше?"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Повторить генерацию", callback_data="retry_generation")],
            [InlineKeyboardButton("📝 Изменить данные", callback_data="edit_data")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            await update.callback_query.message.reply_text(
                error_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                error_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return DocumentStates.DOCUMENT_GENERATION.value


async def generate_document_with_gigachat(doc_type: str, doc_subtype: str, document_data: Dict[str, str]) -> str:
    """
    Генерирует документ с помощью GigaChat API
    """
    # Формируем системный промпт для генерации документа
    system_prompt = get_document_generation_prompt(doc_type, doc_subtype)
    
    # Формируем пользовательский промпт с данными
    user_prompt = format_user_data_for_prompt(doc_type, doc_subtype, document_data)
    
    # Генерируем документ
    response = await gigachat_client.generate_document(system_prompt, user_prompt)
    
    return response


def get_document_generation_prompt(doc_type: str, doc_subtype: str) -> str:
    """
    Возвращает системный промпт для генерации конкретного типа документа
    """
    prompts = {
        "contract": {
            "rent": """Ты профессиональный юрист, специализирующийся на договорах аренды.
            
Создай юридически корректный договор аренды на основе предоставленных данных.
Документ должен содержать:
1. Полное наименование документа с указанием места и даты
2. Данные сторон (арендодатель и арендатор)
3. Предмет договора с точным описанием имущества
4. Размер арендной платы и порядок ее внесения
5. Срок действия договора
6. Права и обязанности сторон
7. Ответственность сторон
8. Порядок расторжения договора
9. Подписи сторон

Используй официальный деловой стиль, соблюдай юридическую терминологию.
Текст должен быть структурированным и профессиональным.""",
            
            "sale": """Ты профессиональный юрист, специализирующийся на договорах купли-продажи.
            
Создай юридически корректный договор купли-продажи на основе предоставленных данных.
Документ должен содержать:
1. Полное наименование документа с указанием места и даты
2. Данные сторон (продавец и покупатель)
3. Предмет договора с подробным описанием товара
4. Цена и порядок расчетов
5. Порядок передачи товара
6. Права и обязанности сторон
7. Ответственность сторон
8. Гарантии и возврат
9. Подписи сторон

Используй официальный деловой стиль, соблюдай юридическую терминологию."""
        },
        "lawsuit": {
            "debt": """Ты профессиональный юрист, специализирующийся на исковых заявлениях.
            
Создай юридически корректное исковое заявление о взыскании долга на основе предоставленных данных.
Документ должен содержать:
1. Наименование суда
2. Данные истца и ответчика
3. Цена иска
4. Обстоятельства, на которых основаны требования
5. Доказательства, подтверждающие требования
6. Перечень прилагаемых документов
7. Дата и подпись
8. Ссылки на соответствующие статьи ГК РФ и ГПК РФ

Используй строгий юридический стиль, соблюдай процессуальные требования."""
        },
        "claim": {
            "payment": """Ты профессиональный юрист, специализирующийся на досудебных претензиях.
            
Создай юридически корректную досудебную претензию о взыскании долга на основе предоставленных данных.
Документ должен содержать:
1. Данные кредитора и должника
2. Основание возникновения долга
3. Размер задолженности
4. Требование о погашении долга
5. Срок для добровольного исполнения (обычно 10 дней)
6. Предупреждение об обращении в суд
7. Перечень прилагаемых документов
8. Дата и подпись

Тон должен быть официальным, но корректным."""
        }
    }
    
    # Возвращаем промпт для конкретного типа или базовый
    if doc_type in prompts and doc_subtype in prompts[doc_type]:
        return prompts[doc_type][doc_subtype]
    
    # Базовый промпт для неопределенных типов
    return """Ты профессиональный юрист. Создай юридически корректный документ на основе предоставленных данных.
    Документ должен быть структурированным, содержать все необходимые элементы и соответствовать российскому законодательству.
    Используй официальный деловой стиль и юридическую терминологию."""


def format_user_data_for_prompt(doc_type: str, doc_subtype: str, document_data: Dict[str, str]) -> str:
    """
    Форматирует данные пользователя в промпт для GigaChat
    """
    data_text = "Создай документ на основе следующих данных:\n\n"
    
    for key, value in document_data.items():
        data_text += f"• {key}: {value}\n"
    
    data_text += "\nСоздай полноценный юридический документ с учетом всех требований российского законодательства."
    
    return data_text


async def show_generated_document(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = False) -> int:
    """
    Показывает сгенерированный документ пользователю
    """
    generated_document = context.user_data['generated_document']
    
    # Обрезаем документ если он слишком длинный для сообщения
    max_length = 3500  # Оставляем место для кнопок и форматирования
    display_document = generated_document
    
    if len(generated_document) > max_length:
        display_document = generated_document[:max_length] + "\n\n... (документ обрезан для отображения)"
    
    result_text = (
        f"📄 **Ваш документ готов!**\n\n"
        f"```\n{display_document}\n```\n\n"
        "Проверьте документ и выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять документ", callback_data="accept_document")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="edit_document")],
        [InlineKeyboardButton("➕ Дополнить", callback_data="supplement_document")],
        [InlineKeyboardButton("🔄 Перегенерировать", callback_data="regenerate_document")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if is_callback:
            await update.callback_query.message.reply_text(
                result_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                result_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        # Если не удалось отправить с Markdown, пробуем без него
        logger.warning(f"Ошибка отправки с Markdown: {e}")
        result_text_plain = (
            f"📄 Ваш документ готов!\n\n"
            f"{display_document}\n\n"
            "Проверьте документ и выберите действие:"
        )
        
        if is_callback:
            await update.callback_query.message.reply_text(
                result_text_plain,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                result_text_plain,
                reply_markup=reply_markup
            )
    
    return DocumentStates.DOCUMENT_REVIEW.value


async def handle_document_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик действий с готовым документом
    """
    query = update.callback_query
    await query.answer()
    
    if query.data == "accept_document":
        return await finalize_document(update, context)
    elif query.data == "edit_document":
        return await start_document_editing(update, context)
    elif query.data == "supplement_document":
        return await start_document_supplement(update, context)
    elif query.data == "regenerate_document":
        return await regenerate_document(update, context)
    
    return DocumentStates.DOCUMENT_REVIEW.value


async def start_document_editing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало редактирования документа
    """
    query = update.callback_query
    
    edit_text = (
        "✏️ **Редактирование документа**\n\n"
        "Опишите, что нужно изменить в документе:\n"
        "• Исправить ошибки\n"
        "• Изменить формулировки\n"
        "• Добавить/убрать разделы\n"
        "• Изменить данные\n\n"
        "Напишите ваши пожелания:"
    )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        edit_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return DocumentStates.DOCUMENT_EDITING.value


async def start_document_supplement(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало дополнения документа
    """
    query = update.callback_query
    
    supplement_text = (
        "➕ **Дополнение документа**\n\n"
        "Укажите, что нужно добавить к документу:\n"
        "• Дополнительные условия\n"
        "• Новые разделы\n"
        "• Приложения\n"
        "• Специальные оговорки\n\n"
        "Опишите ваши дополнения:"
    )
    
    keyboard = [
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_supplement")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        supplement_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return DocumentStates.DOCUMENT_EDITING.value


async def process_document_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка изменений документа
    """
    user_changes = update.message.text
    
    # Показываем индикатор обработки
    await update.message.chat.send_action(ChatAction.TYPING)
    
    processing_text = (
        "🔄 **Обработка изменений...**\n\n"
        f"📝 Ваши пожелания: *{user_changes}*\n\n"
        "⏳ Применяю изменения к документу..."
    )
    
    await update.message.reply_text(
        processing_text,
        parse_mode='Markdown'
    )
    
    try:
        # Получаем текущий документ
        current_document = context.user_data['generated_document']
        
        # Формируем промпт для изменений
        edit_prompt = f"""
Исходный документ:
{current_document}

Требуемые изменения:
{user_changes}

Внеси указанные изменения в документ, сохранив его юридическую корректность и структуру.
"""
        
        # Генерируем обновленный документ
        system_prompt = "Ты профессиональный юрист. Внеси изменения в документ согласно пожеланиям пользователя, сохранив юридическую корректность и профессиональную структуру."
        
        updated_document = await generate_document_with_gigachat("edit", "changes", {"edit_prompt": edit_prompt})
        
        # Сохраняем обновленный документ
        context.user_data['generated_document'] = updated_document
        
        success_text = (
            "✅ **Изменения применены!**\n\n"
            "Документ обновлен согласно вашим пожеланиям.\n"
            "Проверьте результат и выберите действие:"
        )
        
        await update.message.reply_text(success_text, parse_mode='Markdown')
        
        # Показываем обновленный документ
        return await show_generated_document(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании документа: {e}")
        
        error_text = (
            "❌ **Ошибка редактирования**\n\n"
            "Не удалось применить изменения.\n"
            "Попробуйте:\n"
            "• Уточнить пожелания\n"
            "• Упростить требования\n"
            "• Повторить попытку\n\n"
            "Что делаем?"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="edit_document")],
            [InlineKeyboardButton("⬅️ К документу", callback_data="show_document")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            error_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return DocumentStates.DOCUMENT_REVIEW.value


async def regenerate_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Перегенерация документа
    """
    query = update.callback_query
    
    await query.message.reply_text(
        "🔄 **Перегенерация документа...**\n\n"
        "⏳ Создаю новую версию документа с теми же данными...",
        parse_mode='Markdown'
    )
    
    # Перегенерируем с теми же данными
    return await start_document_generation(update, context, is_callback=True)


async def finalize_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Финализация документа - создание DOCX и сохранение
    """
    query = update.callback_query
    
    finalization_text = (
        "💾 **Финализация документа...**\n\n"
        "⏳ Создаю файл Word (.docx)...\n"
        "📤 Подготавливаю к загрузке...\n\n"
        "*Это займет несколько секунд*"
    )
    
    await query.message.reply_text(
        finalization_text,
        parse_mode='Markdown'
    )
    
    try:
        # Создаем DOCX файл
        docx_file_path = await create_docx_document(context.user_data['generated_document'], context.user_data)
        
        # Отправляем файл пользователю
        with open(docx_file_path, 'rb') as doc_file:
            await query.message.reply_document(
                document=doc_file,
                filename=get_document_filename(context.user_data),
                caption=(
                    "📄 **Ваш документ готов!**\n\n"
                    "✅ Файл создан в формате Word (.docx)\n"
                    "📁 Можете скачать и использовать\n\n"
                    "🔍 Обязательно проверьте документ перед использованием!"
                ),
                parse_mode='Markdown'
            )
        
        # Запрашиваем оценку
        return await request_document_rating(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка создания DOCX: {e}")
        
        error_text = (
            "❌ **Ошибка создания файла**\n\n"
            "Не удалось создать DOCX файл.\n"
            "Документ остается доступен в чате.\n\n"
            "Попробуйте:\n"
            "• Скопировать текст документа\n"
            "• Повторить создание файла\n"
            "• Обратиться в поддержку"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Повторить создание", callback_data="retry_docx")],
            [InlineKeyboardButton("📋 Показать текст", callback_data="show_document")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            error_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return DocumentStates.DOCUMENT_FINALIZATION.value


async def create_docx_document(document_text: str, user_data: Dict[str, Any]) -> str:
    """
    Создает DOCX файл из текста документа
    """
    try:
        from docx import Document
        from docx.shared import Inches
        import os
        import tempfile
        
        # Создаем новый документ Word
        doc = Document()
        
        # Устанавливаем поля
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1.25)
            section.right_margin = Inches(1.25)
        
        # Добавляем текст документа
        # Разбиваем на абзацы
        paragraphs = document_text.split('\n\n')
        
        for paragraph_text in paragraphs:
            if paragraph_text.strip():
                # Проверяем, является ли это заголовком
                if (paragraph_text.strip().isupper() or 
                    paragraph_text.strip().startswith('ДОГОВОР') or
                    paragraph_text.strip().startswith('ИСКОВОЕ') or
                    paragraph_text.strip().startswith('ПРЕТЕНЗИЯ')):
                    # Добавляем как заголовок
                    heading = doc.add_heading(paragraph_text.strip(), level=1)
                    heading.alignment = 1  # Центрирование
                else:
                    # Добавляем как обычный абзац
                    p = doc.add_paragraph(paragraph_text.strip())
                    p.alignment = 3  # Выравнивание по ширине
        
        # Создаем временный файл
        temp_dir = tempfile.gettempdir()
        filename = get_document_filename(user_data)
        file_path = os.path.join(temp_dir, filename)
        
        # Сохраняем документ
        doc.save(file_path)
        
        return file_path
        
    except ImportError:
        # Если библиотека python-docx не установлена
        raise Exception("Библиотека python-docx не найдена")
    except Exception as e:
        raise Exception(f"Ошибка создания DOCX: {e}")


def get_document_filename(user_data: Dict[str, Any]) -> str:
    """
    Генерирует имя файла для документа
    """
    doc_type = user_data.get('document_type', 'document')
    doc_subtype = user_data.get('document_subtype', 'general')
    
    # Переводим типы в читаемые имена
    type_names = {
        'contract': 'Договор',
        'lawsuit': 'Исковое_заявление',
        'claim': 'Претензия',
        'agreement': 'Соглашение',
        'power_of_attorney': 'Доверенность',
        'application': 'Заявление',
        'protocol': 'Протокол',
        'act': 'Акт'
    }
    
    subtype_names = {
        'rent': 'аренды',
        'sale': 'купли_продажи',
        'debt': 'взыскание_долга',
        'payment': 'взыскание_долга',
        'general': 'общий'
    }
    
    type_name = type_names.get(doc_type, 'Документ')
    subtype_name = subtype_names.get(doc_subtype, doc_subtype)
    
    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    
    return f"{type_name}_{subtype_name}_{date_str}.docx"


async def request_document_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Запрос оценки документа от пользователя
    """
    rating_text = (
        "⭐ **Оцените качество документа**\n\n"
        "Помогите нам улучшить сервис!\n"
        "Оцените созданный документ от 1 до 5:"
    )
    
    keyboard = []
    for i in range(1, 6):
        stars = "⭐" * i
        keyboard.append([InlineKeyboardButton(f"{stars} {i}", callback_data=f"rate_{i}")])
    
    keyboard.append([InlineKeyboardButton("➡️ Пропустить оценку", callback_data="skip_rating")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.reply_text(
        rating_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return DocumentStates.DOCUMENT_FINALIZATION.value


async def handle_document_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка оценки документа
    """
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("rate_"):
        rating = int(query.data.replace("rate_", ""))
        
        # TODO: Сохранить оценку в Supabase
        # await save_document_rating(context.user_data, rating)
        
        thank_you_text = (
            f"🙏 **Спасибо за оценку: {rating} ⭐**\n\n"
            "Ваша обратная связь поможет нам улучшить качество документов!\n\n"
            "📄 **Что еще могу для вас сделать?**"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Создать новый документ", callback_data="new_document")],
            [InlineKeyboardButton("💬 Получить консультацию", callback_data="consultation")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
    else:  # skip_rating
        thank_you_text = (
            "👍 **Понятно, спасибо!**\n\n"
            "📄 **Что еще могу для вас сделать?**"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Создать новый документ", callback_data="new_document")],
            [InlineKeyboardButton("💬 Получить консультацию", callback_data="consultation")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        thank_you_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Очищаем данные документа
    context.user_data.pop('document_data', None)
    context.user_data.pop('document_type', None)
    context.user_data.pop('document_subtype', None)
    context.user_data.pop('generated_document', None)
    
    return ConversationHandler.END