#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент для работы с GigaChat API
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
import httpx
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE

logger = logging.getLogger(__name__)


class GigaChatClient:
    """
    Клиент для работы с GigaChat API
    """
    
    def __init__(self):
        """Инициализация клиента GigaChat"""
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Инициализация GigaChat клиента
        """
        try:
            self.client = GigaChat(
                credentials=GIGACHAT_CREDENTIALS,
                scope=GIGACHAT_SCOPE,
                model="GigaChat",
                verify_ssl_certs=False
            )
            logger.info("GigaChat клиент успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации GigaChat: {e}")
            raise
    
    async def generate_consultation(
        self, 
        user_question: str, 
        category: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Генерация юридической консультации
        
        Args:
            user_question: Вопрос пользователя
            category: Категория права
            user_context: Дополнительный контекст пользователя
            
        Returns:
            Ответ консультации
        """
        try:
            # Системный промпт для юридических консультаций
            system_prompt = self._create_consultation_system_prompt(category)
            
            # Форматируем пользовательский запрос
            formatted_question = self._format_user_question(user_question, category, user_context)
            
            # Создаём сообщения для модели
            messages = [
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=system_prompt
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=formatted_question
                )
            ]
            
            # Отправляем запрос к GigaChat
            logger.info(f"Отправка запроса в GigaChat. Категория: {category}")
            
            # Используем asyncio.to_thread для синхронного вызова
            chat_request = Chat(
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            response = await asyncio.to_thread(self.client.chat, chat_request)
            
            # Получаем ответ
            if response.choices and len(response.choices) > 0:
                answer_content = response.choices[0].message.content
            else:
                raise Exception("Пустой ответ от GigaChat")
            
            # Форматируем ответ
            formatted_response = self._format_consultation_response(
                answer_content, 
                category, 
                user_question
            )
            
            logger.info("Консультация успешно сгенерирована")
            return formatted_response
            
        except Exception as e:
            logger.error(f"Ошибка генерации консультации: {e}")
            return self._get_error_response(category)
    
    def _create_consultation_system_prompt(self, category: str) -> str:
        """
        Создание системного промпта для консультаций
        """
        base_prompt = """Ты — профессиональный AI-юрист с глубокими знаниями российского законодательства. 

ТВОЯ РОЛЬ:
• Предоставлять точные юридические консультации
• Объяснять сложные правовые концепции простым языком
• Ссылаться на конкретные статьи законов РФ
• Давать практические рекомендации

ПРИНЦИПЫ РАБОТЫ:
• Эмпатия и поддержка пользователя
• Структурированный и понятный ответ
• Объяснение юридических терминов
• Рекомендации по дальнейшим действиям
• Указание на необходимость консультации с практикующим юристом при сложных вопросах

ФОРМАТ ОТВЕТА:
1. Краткий анализ ситуации
2. Применимые правовые нормы (со ссылками на статьи)
3. Практические рекомендации
4. Объяснение терминов (если есть)
5. Дальнейшие действия

ВАЖНО:
• Используй актуальные нормы российского права
• Будь точным и конкретным
• Избегай общих фраз
• Проявляй эмпатию к ситуации пользователя"""

        category_specific = {
            "Гражданское право": "\n\nСПЕЦИАЛИЗАЦИЯ: Договоры, обязательства, собственность, наследство, возмещение ущерба.",
            "Уголовное право": "\n\nСПЕЦИАЛИЗАЦИЯ: Преступления, наказания, процессуальные права, защита в суде.",
            "Семейное право": "\n\nСПЕЦИАЛИЗАЦИЯ: Брак, развод, алименты, опека, права детей.",
            "Трудовое право": "\n\nСПЕЦИАЛИЗАЦИЯ: Трудовые договоры, увольнения, зарплата, отпуска, трудовые споры.",
            "Жилищное право": "\n\nСПЕЦИАЛИЗАЦИЯ: Аренда, покупка/продажа жилья, ЖКХ, приватизация.",
            "Административное право": "\n\nСПЕЦИАЛИЗАЦИЯ: Штрафы, административная ответственность, госуслуги.",
            "Другое": "\n\nСПЕЦИАЛИЗАЦИЯ: Общие правовые вопросы, межотраслевые ситуации."
        }
        
        return base_prompt + category_specific.get(category, category_specific["Другое"])
    
    def _format_user_question(
        self, 
        question: str, 
        category: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Форматирование вопроса пользователя
        """
        formatted = f"КАТЕГОРИЯ: {category}\n\n"
        
        # Проверяем, является ли это продолжением консультации
        if context and context.get('is_continuation', False):
            formatted += "РЕЖИМ: Продолжение консультации\n\n"
            
            # Добавляем историю диалога
            consultation_history = context.get('consultation_history', [])
            if consultation_history:
                formatted += "ИСТОРИЯ ДИАЛОГА:\n"
                for idx, message in enumerate(consultation_history[-6:], 1):  # Последние 6 сообщений
                    role = "ПОЛЬЗОВАТЕЛЬ" if message['role'] == 'user' else "ЮРИСТ"
                    content = message['content'][:200] + "..." if len(message['content']) > 200 else message['content']
                    formatted += f"{idx}. {role}: {content}\n\n"
            
            formatted += f"НОВЫЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{question}\n\n"
            formatted += "Учти контекст предыдущих сообщений и дай развернутый ответ на новый вопрос, связывая его с предыдущим обсуждением."
        else:
            formatted += f"ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{question}\n\n"
            formatted += "Предоставь развернутую юридическую консультацию согласно указанному формату."
        
        if context and not context.get('is_continuation', False):
            formatted += "\nДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ:\n"
            for key, value in context.items():
                formatted += f"• {key}: {value}\n"
        
        return formatted
    
    def _format_consultation_response(
        self, 
        response: str, 
        category: str, 
        original_question: str
    ) -> str:
        """
        Форматирование ответа консультации для Telegram
        """
        # Обрезаем вопрос для отображения
        question_preview = original_question[:100] + "..." if len(original_question) > 100 else original_question
        
        formatted_response = (
            f"📋 **Консультация по категории: {category}**\n\n"
            f"❓ **Ваш вопрос:** {question_preview}\n\n"
            f"⚖️ **Юридический анализ:**\n\n"
            f"{response}\n\n"
            f"❓ Есть дополнительные вопросы? Используйте /consult снова."
        )
        
        return formatted_response
    
    def _get_error_response(self, category: str) -> str:
        """
        Ответ при ошибке генерации
        """
        return (
            f"📋 **Консультация по категории: {category}**\n\n"
            "❌ Извините, возникла техническая ошибка при подготовке консультации.\n\n"
            "🔄 Попробуйте:\n"
            "• Переформулировать вопрос\n"
            "• Использовать команду /consult снова\n"
            "• Обратиться в поддержку\n\n"
            "📞 При срочных вопросах рекомендуем обратиться к практикующему юристу."
        )
    
    async def test_connection(self) -> bool:
        """
        Тестирование соединения с GigaChat
        """
        try:
            test_messages = [
                Messages(
                    role=MessagesRole.USER,
                    content="Привет! Это тестовое сообщение."
                )
            ]
            
            chat_request = Chat(
                messages=test_messages,
                temperature=0.1,
                max_tokens=50
            )
            
            response = await asyncio.to_thread(self.client.chat, chat_request)
            logger.info("Тест соединения с GigaChat прошёл успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка тестирования соединения с GigaChat: {e}")
            return False

    async def generate_document(self, system_prompt: str, user_prompt: str) -> str:
        """
        Генерация юридического документа с помощью GigaChat
        """
        try:
            # Используем специальный системный промпт для генерации документов
            full_system_prompt = f"""{system_prompt}

ВАЖНЫЕ ТРЕБОВАНИЯ:
- Создай полноценный юридический документ
- Используй профессиональную юридическую терминологию
- Соблюдай структуру документа согласно российскому законодательству
- Все поля должны быть заполнены на основе предоставленных данных
- Добавь текущую дату в нужном формате
- Документ должен быть готов к использованию"""
            
            # Создаём сообщения для модели
            messages = [
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=full_system_prompt
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=user_prompt
                )
            ]
            
            # Отправляем запрос к GigaChat
            chat_request = Chat(
                messages=messages,
                temperature=0.5,  # Меньше творчества для документов
                max_tokens=3000   # Больше токенов для документов
            )
            
            response = await asyncio.to_thread(self.client.chat, chat_request)
            
            # Получаем ответ
            if response.choices and len(response.choices) > 0:
                generated_document = response.choices[0].message.content
                return generated_document
            else:
                return self._get_document_fallback()
                
        except Exception as e:
            logger.error(f"Ошибка при генерации документа: {e}")
            return self._get_document_fallback()
    
    
    def _get_document_fallback(self) -> str:
        """
        Возвращает базовый шаблон документа в случае ошибки
        """
        return """ДОКУМЕНТ
        
К сожалению, произошла техническая ошибка при генерации документа.
        
Рекомендуем:
1. Проверить корректность введенных данных
2. Повторить попытку через несколько минут
3. Обратиться к юристу для ручного составления документа

Приносим извинения за временные неудобства.

Дата: ______________
Подпись: ______________"""


# Глобальный экземпляр клиента
gigachat_client = GigaChatClient()