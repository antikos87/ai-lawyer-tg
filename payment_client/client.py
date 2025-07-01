#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент для работы с YooKassa API
"""

import logging
import uuid
from typing import Dict, Any, Optional
import yookassa as yookassa_lib
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

logger = logging.getLogger(__name__)


class YooKassaClient:
    """
    Клиент для работы с платежами YooKassa
    """
    
    # Цены тарифов в копейках
    SUBSCRIPTION_PRICES = {
        'basic': 79000,     # 790₽
        'premium': 149000,  # 1490₽
        'corporate': 399000  # 3990₽
    }
    
    SUBSCRIPTION_NAMES = {
        'basic': 'AI-Юрист Базовый',
        'premium': 'AI-Юрист Премиум', 
        'corporate': 'AI-Юрист Корпоративный'
    }
    
    def __init__(self):
        """Инициализация YooKassa клиента"""
        try:
            yookassa_lib.Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
            logger.info("YooKassa клиент успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации YooKassa: {e}")
            raise

    async def create_payment(self, telegram_id: int, subscription_type: str, 
                           return_url: str = None) -> Dict[str, Any]:
        """
        Создает платеж для подписки
        
        Args:
            telegram_id: ID пользователя в Telegram
            subscription_type: Тип подписки (basic, premium, corporate)
            return_url: URL для возврата после оплаты
            
        Returns:
            Словарь с данными платежа
        """
        try:
            if subscription_type not in self.SUBSCRIPTION_PRICES:
                raise ValueError(f"Неизвестный тип подписки: {subscription_type}")
            
            amount = self.SUBSCRIPTION_PRICES[subscription_type]
            description = f"{self.SUBSCRIPTION_NAMES[subscription_type]} - 1 месяц"
            
            # Генерируем уникальный идемпотентный ключ
            idempotency_key = str(uuid.uuid4())
            
            # Данные для платежа
            payment_data = {
                "amount": {
                    "value": f"{amount / 100:.2f}",  # Конвертируем копейки в рубли
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/AIlawer_bot"
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "telegram_id": str(telegram_id),
                    "subscription_type": subscription_type,
                    "order_id": f"sub_{telegram_id}_{subscription_type}_{idempotency_key[:8]}"
                }
            }
            
            # Создаем платеж
            payment = yookassa_lib.Payment.create(payment_data, idempotency_key)
            
            logger.info(f"Создан платеж {payment.id} для пользователя {telegram_id}, тариф {subscription_type}")
            
            return {
                'payment_id': payment.id,
                'confirmation_url': payment.confirmation.confirmation_url,
                'amount': amount,
                'currency': 'RUB',
                'description': description,
                'status': payment.status,
                'created_at': payment.created_at.isoformat() if hasattr(payment.created_at, 'isoformat') else str(payment.created_at),
                'metadata': payment.metadata
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа для {telegram_id}: {e}")
            raise

    async def get_payment_info(self, payment_id: str) -> Dict[str, Any]:
        """
        Получает информацию о платеже
        """
        try:
            payment = yookassa_lib.Payment.find_one(payment_id)
            
            # Проверяем доступные атрибуты
            paid_at = None
            if hasattr(payment, 'captured_at') and payment.captured_at:
                paid_at = payment.captured_at.isoformat() if hasattr(payment.captured_at, 'isoformat') else str(payment.captured_at)
            elif hasattr(payment, 'authorized_at') and payment.authorized_at:
                paid_at = payment.authorized_at.isoformat() if hasattr(payment.authorized_at, 'isoformat') else str(payment.authorized_at)
            
            return {
                'payment_id': payment.id,
                'status': payment.status,
                'amount': int(float(payment.amount.value) * 100),  # В копейках
                'currency': payment.amount.currency,
                'description': payment.description,
                'created_at': payment.created_at.isoformat() if hasattr(payment.created_at, 'isoformat') else str(payment.created_at),
                'paid_at': paid_at,
                'metadata': payment.metadata
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о платеже {payment_id}: {e}")
            raise

    async def cancel_payment(self, payment_id: str, reason: str = "Отмена пользователем") -> Dict[str, Any]:
        """
        Отменяет платеж
        """
        try:
            payment = yookassa_lib.Payment.find_one(payment_id)
            
            if payment.status not in ['pending', 'waiting_for_capture']:
                raise ValueError(f"Платеж {payment_id} нельзя отменить (статус: {payment.status})")
            
            cancelled_payment = yookassa_lib.Payment.cancel(payment_id, str(uuid.uuid4()))
            
            logger.info(f"Платеж {payment_id} отменен: {reason}")
            
            return {
                'payment_id': cancelled_payment.id,
                'status': cancelled_payment.status,
                'cancellation_reason': reason
            }
            
        except Exception as e:
            logger.error(f"Ошибка отмены платежа {payment_id}: {e}")
            raise

    async def create_refund(self, payment_id: str, amount_kopecks: Optional[int] = None, 
                          reason: str = "Возврат по запросу") -> Dict[str, Any]:
        """
        Создает возврат платежа
        """
        try:
            payment = yookassa_lib.Payment.find_one(payment_id)
            
            if payment.status != 'succeeded':
                raise ValueError(f"Возврат возможен только для успешных платежей (статус: {payment.status})")
            
            # Если сумма не указана, возвращаем полную стоимость
            if amount_kopecks is None:
                amount_kopecks = int(float(payment.amount.value) * 100)
            
            from yookassa import Refund
            
            refund_data = {
                "amount": {
                    "value": f"{amount_kopecks / 100:.2f}",
                    "currency": payment.amount.currency
                },
                "payment_id": payment_id,
                "description": reason
            }
            
            refund = yookassa_lib.Refund.create(refund_data, str(uuid.uuid4()))
            
            logger.info(f"Создан возврат {refund.id} для платежа {payment_id}")
            
            return {
                'refund_id': refund.id,
                'payment_id': payment_id,
                'amount': amount_kopecks,
                'status': refund.status,
                'description': reason,
                'created_at': refund.created_at.isoformat() if hasattr(refund.created_at, 'isoformat') else str(refund.created_at)
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания возврата для платежа {payment_id}: {e}")
            raise

    async def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает webhook от YooKassa
        """
        try:
            # Проверяем тип события
            event_type = webhook_data.get('event')
            payment_data = webhook_data.get('object', {})
            
            if not event_type or not payment_data:
                raise ValueError("Некорректные данные webhook")
            
            payment_id = payment_data.get('id')
            status = payment_data.get('status')
            metadata = payment_data.get('metadata', {})
            
            result = {
                'event_type': event_type,
                'payment_id': payment_id,
                'status': status,
                'telegram_id': metadata.get('telegram_id'),
                'subscription_type': metadata.get('subscription_type'),
                'order_id': metadata.get('order_id'),
                'processed_at': webhook_data.get('created_at')
            }
            
            logger.info(f"Обработан webhook: {event_type} для платежа {payment_id}, статус {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки webhook: {e}")
            raise

    def get_subscription_info(self, subscription_type: str) -> Dict[str, Any]:
        """
        Возвращает информацию о тарифе
        """
        if subscription_type not in self.SUBSCRIPTION_PRICES:
            raise ValueError(f"Неизвестный тип подписки: {subscription_type}")
        
        price_kopecks = self.SUBSCRIPTION_PRICES[subscription_type]
        
        return {
            'type': subscription_type,
            'name': self.SUBSCRIPTION_NAMES[subscription_type],
            'price_kopecks': price_kopecks,
            'price_rubles': price_kopecks / 100,
            'duration_days': 30,
            'currency': 'RUB'
        }

    def get_all_subscriptions_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает информацию о всех тарифах
        """
        result = {}
        for sub_type in self.SUBSCRIPTION_PRICES.keys():
            result[sub_type] = self.get_subscription_info(sub_type)
        
        return result


# Глобальный экземпляр клиента
yookassa_client = YooKassaClient() 