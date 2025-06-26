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


    async def analyze_document(
        self, 
        document_text: str, 
        analysis_type: str,
        filename: str = "документ"
    ) -> str:
        """
        Анализ юридического документа
        
        Args:
            document_text: Извлеченный текст документа
            analysis_type: Тип анализа
            filename: Имя файла для контекста
            
        Returns:
            Результат анализа документа
        """
        try:
            # Системный промпт для анализа документов
            system_prompt = self._create_document_analysis_system_prompt(analysis_type)
            
            # Форматируем запрос для анализа
            formatted_request = self._format_document_analysis_request(
                document_text, analysis_type, filename
            )
            
            # Создаём сообщения для модели
            messages = [
                Messages(
                    role=MessagesRole.SYSTEM,
                    content=system_prompt
                ),
                Messages(
                    role=MessagesRole.USER,
                    content=formatted_request
                )
            ]
            
            # Отправляем запрос к GigaChat
            logger.info(f"Отправка документа на анализ. Тип: {analysis_type}, файл: {filename}")
            
            chat_request = Chat(
                messages=messages,
                temperature=0.3,  # Более низкая температура для точного анализа
                max_tokens=3000   # Больше токенов для подробного анализа
            )
            
            response = await asyncio.to_thread(self.client.chat, chat_request)
            
            # Получаем ответ
            if response.choices and len(response.choices) > 0:
                analysis_content = response.choices[0].message.content
            else:
                raise Exception("Пустой ответ от GigaChat")
            
            # Форматируем результат анализа
            formatted_analysis = self._format_document_analysis_response(
                analysis_content, analysis_type, filename
            )
            
            logger.info(f"Анализ документа успешно завершен. Тип: {analysis_type}")
            return formatted_analysis
            
        except Exception as e:
            logger.error(f"Ошибка анализа документа: {e}")
            return self._get_document_analysis_error_response(analysis_type)

    def _create_document_analysis_system_prompt(self, analysis_type: str) -> str:
        """
        Создание системного промпта для анализа документов
        """
        base_prompt = """Ты — профессиональный AI-юрист, специализирующийся на анализе юридических документов. 

ТВОЯ РОЛЬ:
• Проводить глубокий анализ юридических документов
• Выявлять проблемы, риски и несоответствия
• Давать конкретные рекомендации по улучшению
• Ссылаться на применимые нормы российского права

ПРИНЦИПЫ АНАЛИЗА:
• Тщательность и внимание к деталям
• Структурированная подача информации
• Конкретные примеры и цитаты из документа
• Практические рекомендации
• Оценка юридических рисков

ВАЖНО:
• Анализируй документ в контексте российского законодательства
• Будь конкретным и точным
• Приводи примеры из текста документа
• Указывай номера статей и пунктов при ссылках на законы"""

        analysis_specific = {
            "law_compliance": """

СПЕЦИАЛИЗАЦИЯ: ПРОВЕРКА СООТВЕТСТВИЯ ЗАКОНУ
• Анализ соответствия документа действующему законодательству РФ
• Выявление противоречий с федеральными законами и подзаконными актами
• Оценка правомерности условий и положений
• Проверка соблюдения обязательных требований

ФОРМАТ АНАЛИЗА:
1. **Общая оценка соответствия** (✅/⚠️/❌)
2. **Выявленные нарушения** (конкретные статьи и пункты)
3. **Проблемные условия** (цитаты из документа)
4. **Рекомендации по исправлению**
5. **Правовые риски** при использовании документа""",

            "error_detection": """

СПЕЦИАЛИЗАЦИЯ: ПОИСК ОШИБОК И НЕДОЧЕТОВ
• Выявление юридических, технических и логических ошибок
• Анализ полноты и корректности формулировок
• Проверка последовательности и непротиворечивости
• Оценка ясности и однозначности положений

ФОРМАТ АНАЛИЗА:
1. **Категории найденных ошибок**
2. **Критические ошибки** (могут привести к правовым проблемам)
3. **Технические недочеты** (неточности формулировок)
4. **Рекомендации по исправлению** (конкретные предложения)
5. **Приоритетность исправлений**""",

            "risk_assessment": """

СПЕЦИАЛИЗАЦИЯ: ОЦЕНКА ЮРИДИЧЕСКИХ РИСКОВ
• Анализ потенциальных правовых рисков и угроз
• Оценка вероятности возникновения споров
• Выявление уязвимых мест документа
• Прогнозирование возможных последствий

ФОРМАТ АНАЛИЗА:
1. **Общий уровень риска** (Низкий/Средний/Высокий)
2. **Критические риски** (могут привести к серьезным последствиям)
3. **Умеренные риски** (требуют внимания)
4. **Способы минимизации рисков**
5. **Рекомендации по защите интересов**""",

            "recommendations": """

СПЕЦИАЛИЗАЦИЯ: РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ
• Предложения по оптимизации документа
• Рекомендации по усилению правовой защиты
• Советы по улучшению формулировок
• Предложения дополнительных условий

ФОРМАТ АНАЛИЗА:
1. **Приоритетные улучшения** (критически важные)
2. **Рекомендуемые дополнения** (усиление позиций)
3. **Оптимизация формулировок** (повышение ясности)
4. **Дополнительные гарантии** (снижение рисков)
5. **План внедрения изменений**""",

            "correspondence_analysis": """

СПЕЦИАЛИЗАЦИЯ: АНАЛИЗ ПЕРЕПИСКИ И КОММУНИКАЦИЙ
• Анализ юридической значимости переписки
• Выявление доказательной базы
• Оценка правовых позиций сторон
• Анализ соблюдения процедур

ФОРМАТ АНАЛИЗА:
1. **Ключевые правовые моменты** в переписке
2. **Доказательная ценность** документов
3. **Позиции сторон** и их обоснованность
4. **Процедурные нарушения** (если есть)
5. **Рекомендации по дальнейшим действиям**"""
        }
        
        return base_prompt + analysis_specific.get(analysis_type, analysis_specific["law_compliance"])

    def _format_document_analysis_request(
        self, 
        document_text: str, 
        analysis_type: str, 
        filename: str
    ) -> str:
        """
        Форматирование запроса для анализа документа
        """
        analysis_names = {
            "law_compliance": "ПРОВЕРКА СООТВЕТСТВИЯ ЗАКОНУ",
            "error_detection": "ПОИСК ОШИБОК И НЕДОЧЕТОВ", 
            "risk_assessment": "ОЦЕНКА ЮРИДИЧЕСКИХ РИСКОВ",
            "recommendations": "РЕКОМЕНДАЦИИ ПО УЛУЧШЕНИЮ",
            "correspondence_analysis": "АНАЛИЗ ПЕРЕПИСКИ"
        }
        
        analysis_name = analysis_names.get(analysis_type, "АНАЛИЗ ДОКУМЕНТА")
        
        # Обрезаем текст если он слишком длинный (оставляем место для промпта)
        max_text_length = 8000  # Примерно 2000 токенов для текста документа
        if len(document_text) > max_text_length:
            document_text = document_text[:max_text_length] + "\n\n[ТЕКСТ ОБРЕЗАН ДЛЯ АНАЛИЗА]"
        
        formatted_request = f"""ТИП АНАЛИЗА: {analysis_name}
ФАЙЛ: {filename}
ДЛИНА ТЕКСТА: {len(document_text)} символов

ТЕКСТ ДОКУМЕНТА ДЛЯ АНАЛИЗА:
{'='*50}
{document_text}
{'='*50}

Проведи тщательный анализ представленного документа согласно указанному типу анализа. 
Используй структурированный формат ответа и будь максимально конкретным."""
        
        return formatted_request

    def _format_document_analysis_response(
        self, 
        analysis_content: str, 
        analysis_type: str, 
        filename: str
    ) -> str:
        """
        Форматирование результата анализа документа
        """
        analysis_icons = {
            "law_compliance": "⚖️",
            "error_detection": "🔍", 
            "risk_assessment": "⚠️",
            "recommendations": "💡",
            "correspondence_analysis": "📧"
        }
        
        analysis_names = {
            "law_compliance": "Проверка соответствия закону",
            "error_detection": "Поиск ошибок и недочетов", 
            "risk_assessment": "Оценка юридических рисков",
            "recommendations": "Рекомендации по улучшению",
            "correspondence_analysis": "Анализ переписки"
        }
        
        icon = analysis_icons.get(analysis_type, "📋")
        name = analysis_names.get(analysis_type, "Анализ документа")
        
        header = f"""{icon} **{name}**
📄 **Файл:** {filename}
🤖 **Выполнено:** AI-Юрист

{'='*40}

"""
        
        footer = f"""

{'='*40}
💡 **Важно:** Данный анализ носит рекомендательный характер. Для принятия важных правовых решений рекомендуется консультация с практикующим юристом.

🔄 Хотите провести другой тип анализа этого документа? Используйте команду /analyze"""
        
        return header + analysis_content + footer

    def _get_document_analysis_error_response(self, analysis_type: str) -> str:
        """
        Резервный ответ при ошибке анализа документа
        """
        analysis_names = {
            "law_compliance": "проверки соответствия закону",
            "error_detection": "поиска ошибок", 
            "risk_assessment": "оценки рисков",
            "recommendations": "формирования рекомендаций",
            "correspondence_analysis": "анализа переписки"
        }
        
        analysis_name = analysis_names.get(analysis_type, "анализа документа")
        
        return f"""❌ **Ошибка {analysis_name}**

К сожалению, произошла ошибка при анализе документа.

**Возможные причины:**
• Документ слишком большой или сложный для обработки
• Временные проблемы с AI-сервисом
• Неподдерживаемый формат или кодировка текста

**Рекомендации:**
• Попробуйте загрузить документ меньшего размера
• Убедитесь, что текст читаемый и на русском языке
• Повторите попытку через несколько минут

🔄 Попробуйте снова с командой /analyze"""


# Глобальный экземпляр клиента
gigachat_client = GigaChatClient()