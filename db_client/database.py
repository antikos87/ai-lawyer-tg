#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент для работы с Supabase - управление подписками и пользователями
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Глобальное хранилище для тестового режима
test_subscriptions = {}


class SupabaseClient:
    """
    Клиент для работы с базой данных подписок
    """
    
    def __init__(self):
        """Инициализация Supabase клиента"""
        try:
            # Проверяем если это тестовые данные
            if SUPABASE_URL.startswith('YOUR_') or SUPABASE_KEY.startswith('YOUR_') or 'test' in SUPABASE_URL:
                logger.warning("Используются тестовые данные Supabase - работаем в режиме эмуляции")
                self.client = None
                self.test_mode = True
            else:
                self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
                self.test_mode = False
                logger.info("Supabase клиент успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Supabase: {e}")
            self.client = None
            self.test_mode = True
            logger.warning("Переключился в тестовый режим")

    # === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===

    async def get_or_create_user(self, telegram_id: int, username: str = None, 
                               first_name: str = None, last_name: str = None) -> Dict[str, Any]:
        """
        Получает или создает пользователя
        """
        try:
            # В тестовом режиме возвращаем эмулированного пользователя
            if self.test_mode:
                return {
                    'id': f'test_user_{telegram_id}',
                    'telegram_id': telegram_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'trial_used': False,
                    'created_at': datetime.now().isoformat()
                }
            
            # Проверяем существующего пользователя
            result = self.client.table('users').select('*').eq('telegram_id', telegram_id).execute()
            
            if result.data:
                user = result.data[0]
                logger.info(f"Найден существующий пользователь: {telegram_id}")
                
                # Обновляем данные если изменились
                update_data = {}
                if username and user.get('username') != username:
                    update_data['username'] = username
                if first_name and user.get('first_name') != first_name:
                    update_data['first_name'] = first_name
                if last_name and user.get('last_name') != last_name:
                    update_data['last_name'] = last_name
                
                if update_data:
                    self.client.table('users').update(update_data).eq('id', user['id']).execute()
                    logger.info(f"Обновлены данные пользователя {telegram_id}")
                
                return user
            else:
                # Создаем нового пользователя
                new_user_data = {
                    'telegram_id': telegram_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name
                }
                
                result = self.client.table('users').insert(new_user_data).execute()
                user = result.data[0]
                logger.info(f"Создан новый пользователь: {telegram_id}")
                return user
                
        except Exception as e:
            logger.error(f"Ошибка получения/создания пользователя {telegram_id}: {e}")
            raise

    async def get_user_subscription_status(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получает статус подписки пользователя
        """
        try:
            # Сначала пытаемся получить или создать пользователя
            user = await self.get_or_create_user(telegram_id)
            
            if self.test_mode:
                # В тестовом режиме проверяем глобальное хранилище
                if telegram_id in test_subscriptions:
                    subscription = test_subscriptions[telegram_id]
                    
                    # Проверяем не истекла ли подписка
                    expires_at = datetime.fromisoformat(subscription['expires_at'])
                    if expires_at > datetime.now():
                        return {
                            'has_subscription': True,
                            'subscription_type': subscription['type'],
                            'subscription_id': subscription['id'],
                            'expires_at': expires_at,
                            'is_trial_used': user.get('trial_used', False)
                        }
                    else:
                        # Подписка истекла - удаляем из хранилища
                        del test_subscriptions[telegram_id]
                
                # Нет активной подписки в тестовом режиме
                return {
                    'has_subscription': False,
                    'subscription_type': None,
                    'is_trial_used': user.get('trial_used', False),
                    'expires_at': None
                }
            
            # Получаем реальные данные из БД
            # Простой запрос без JOIN'ов
            result = self.client.table('users').select('*').eq('telegram_id', telegram_id).execute()
            
            if result.data:
                user_data = result.data[0]
                current_subscription_id = user_data.get('current_subscription_id')
                
                if current_subscription_id:
                    # Проверяем активную подписку
                    sub_result = self.client.table('subscriptions').select('*').eq('id', current_subscription_id).eq('status', 'active').execute()
                    
                    if sub_result.data:
                        subscription = sub_result.data[0]
                        expires_at = datetime.fromisoformat(subscription['expires_at'].replace('Z', '+00:00'))
                        
                        # Проверяем не истекла ли подписка
                        if expires_at > datetime.now(expires_at.tzinfo):
                            return {
                                'has_subscription': True,
                                'subscription_type': subscription['type'],
                                'subscription_id': subscription['id'],
                                'expires_at': expires_at,
                                'is_trial_used': user_data.get('trial_used', False)
                            }
                        else:
                            # Подписка истекла
                            await self.expire_subscription(current_subscription_id)
                
                # Нет активной подписки
                return {
                    'has_subscription': False,
                    'subscription_type': None,
                    'is_trial_used': user_data.get('trial_used', False),
                    'expires_at': None
                }
            else:
                # Пользователь не найден - создаем
                return {
                    'has_subscription': False,
                    'subscription_type': None,
                    'is_trial_used': False,
                    'expires_at': None
                }
            
        except Exception as e:
            logger.error(f"Ошибка получения статуса подписки для {telegram_id}: {e}")
            # Возвращаем дефолтные значения при ошибке
            return {
                'has_subscription': False,
                'subscription_type': None,
                'is_trial_used': False,
                'expires_at': None
            }

    # === УПРАВЛЕНИЕ ПОДПИСКАМИ ===

    async def create_trial_subscription(self, telegram_id: int) -> Dict[str, Any]:
        """
        Создает пробную подписку на 1 день
        """
        try:
            # Получаем пользователя
            user = await self.get_or_create_user(telegram_id)
            
            # Проверяем, не использовал ли уже пробный период
            if user.get('trial_used'):
                raise ValueError("Пробный период уже был использован")
            
            # Создаем пробную подписку
            start_time = datetime.now()
            end_time = start_time + timedelta(days=1)
            
            subscription_data = {
                'user_id': user['id'],
                'type': 'trial',
                'status': 'active',
                'started_at': start_time.isoformat(),
                'expires_at': end_time.isoformat(),
                'auto_renewal': False
            }
            
            result = self.client.table('subscriptions').insert(subscription_data).execute()
            subscription = result.data[0]
            
            # Обновляем пользователя
            self.client.table('users').update({
                'current_subscription_id': subscription['id'],
                'trial_used': True,
                'trial_started_at': start_time.isoformat()
            }).eq('id', user['id']).execute()
            
            logger.info(f"Создана пробная подписка для пользователя {telegram_id}")
            return subscription
            
        except Exception as e:
            logger.error(f"Ошибка создания пробной подписки для {telegram_id}: {e}")
            raise

    async def create_paid_subscription(self, telegram_id: int, subscription_type: str, 
                                     payment_id: str) -> Dict[str, Any]:
        """
        Создает платную подписку
        """
        try:
            user = await self.get_or_create_user(telegram_id)
            
            if self.test_mode:
                # В тестовом режиме эмулируем создание подписки
                start_time = datetime.now()
                
                # Эмулируем длительность для разных тарифов
                duration_map = {
                    'trial': 1,
                    'basic': 30,
                    'premium': 30,
                    'corporate': 30
                }
                
                days = duration_map.get(subscription_type, 30)
                end_time = start_time + timedelta(days=days)
                
                subscription = {
                    'id': f'test_sub_{telegram_id}_{subscription_type}',
                    'user_id': user['id'],
                    'type': subscription_type,
                    'status': 'active',
                    'started_at': start_time.isoformat(),
                    'expires_at': end_time.isoformat(),
                    'payment_id': payment_id,
                    'auto_renewal': True
                }
                
                # Сохраняем в глобальное хранилище
                test_subscriptions[telegram_id] = subscription
                
                logger.info(f"[TEST] Создана подписка {subscription_type} для пользователя {telegram_id}")
                return subscription
            
            # Получаем лимиты для типа подписки
            limits_result = self.client.table('subscription_limits').select('*').eq(
                'subscription_type', subscription_type
            ).execute()
            
            if not limits_result.data:
                raise ValueError(f"Неизвестный тип подписки: {subscription_type}")
            
            limits = limits_result.data[0]
            
            # Создаем подписку
            start_time = datetime.now()
            end_time = start_time + timedelta(days=limits['duration_days'])
            
            subscription_data = {
                'user_id': user['id'],
                'type': subscription_type,
                'status': 'active',
                'started_at': start_time.isoformat(),
                'expires_at': end_time.isoformat(),
                'payment_id': payment_id,
                'auto_renewal': True
            }
            
            result = self.client.table('subscriptions').insert(subscription_data).execute()
            subscription = result.data[0]
            
            # Обновляем текущую подписку пользователя
            self.client.table('users').update({
                'current_subscription_id': subscription['id']
            }).eq('id', user['id']).execute()
            
            logger.info(f"Создана подписка {subscription_type} для пользователя {telegram_id}")
            return subscription
            
        except Exception as e:
            logger.error(f"Ошибка создания подписки {subscription_type} для {telegram_id}: {e}")
            raise

    async def expire_subscription(self, subscription_id: str) -> None:
        """
        Помечает подписку как истекшую
        """
        try:
            self.client.table('subscriptions').update({
                'status': 'expired'
            }).eq('id', subscription_id).execute()
            
            logger.info(f"Подписка {subscription_id} помечена как истекшая")
            
        except Exception as e:
            logger.error(f"Ошибка истечения подписки {subscription_id}: {e}")
            raise

    async def renew_subscription(self, telegram_id: int, payment_id: str) -> Dict[str, Any]:
        """
        Продлевает текущую подписку на тот же тариф
        """
        try:
            # Получаем статус текущей подписки
            status = await self.get_user_subscription_status(telegram_id)
            
            if not status['has_subscription']:
                raise ValueError("Нет активной подписки для продления")
            
            current_subscription_id = status['subscription_id']
            subscription_type = status['subscription_type']
            current_expires_at = status['expires_at']
            
            user = await self.get_or_create_user(telegram_id)
            
            if self.test_mode:
                # В тестовом режиме обновляем существующую подписку
                subscription = test_subscriptions.get(telegram_id)
                if subscription:
                    # Продлеваем от текущей даты истечения
                    new_expires_at = current_expires_at + timedelta(days=30)
                    subscription['expires_at'] = new_expires_at.isoformat()
                    subscription['payment_id'] = payment_id
                    
                    logger.info(f"[TEST] Продлена подписка {subscription_type} для пользователя {telegram_id} до {new_expires_at}")
                    return subscription
                else:
                    raise ValueError("Не найдена активная подписка в тестовом режиме")
            
            # Получаем лимиты для типа подписки
            limits_result = self.client.table('subscription_limits').select('*').eq(
                'subscription_type', subscription_type
            ).execute()
            
            if not limits_result.data:
                raise ValueError(f"Неизвестный тип подписки: {subscription_type}")
            
            limits = limits_result.data[0]
            
            # Продлеваем от текущей даты истечения (не от сегодня)
            new_expires_at = current_expires_at + timedelta(days=limits['duration_days'])
            
            # Обновляем текущую подписку
            result = self.client.table('subscriptions').update({
                'expires_at': new_expires_at.isoformat(),
                'payment_id': payment_id,
                'updated_at': datetime.now().isoformat()
            }).eq('id', current_subscription_id).execute()
            
            if result.data:
                subscription = result.data[0]
                logger.info(f"Продлена подписка {subscription_type} для пользователя {telegram_id} до {new_expires_at}")
                return subscription
            else:
                raise ValueError("Не удалось обновить подписку")
            
        except Exception as e:
            logger.error(f"Ошибка продления подписки для {telegram_id}: {e}")
            raise

    # === УЧЕТ ИСПОЛЬЗОВАНИЯ ===

    async def check_and_log_usage(self, telegram_id: int, action_type: str, 
                                details: Dict = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Проверяет лимиты и логирует использование
        Returns: (can_use, usage_info)
        """
        try:
            # Получаем статус подписки
            status = await self.get_user_subscription_status(telegram_id)
            
            if not status['has_subscription']:
                return False, {
                    'error': 'no_subscription',
                    'message': 'Нет активной подписки',
                    'trial_used': status['is_trial_used']
                }
            
            # Получаем текущее использование
            user = await self.get_or_create_user(telegram_id)
            usage_result = self.client.rpc('get_current_usage', {
                'p_user_id': user['id'],
                'p_subscription_id': status.get('subscription_id')
            }).execute()
            
            current_usage = usage_result.data[0] if usage_result.data else {
                'consultations_used': 0,
                'documents_used': 0,
                'analysis_used': 0
            }
            
            # Получаем лимиты для текущего типа подписки
            subscription_type = status['subscription_type']
            if self.test_mode:
                # В тестовом режиме используем эмулированные лимиты
                limits_map = {
                    'trial': {'consultations_limit': 3, 'documents_limit': 2, 'analysis_limit': 1},
                    'basic': {'consultations_limit': 25, 'documents_limit': 10, 'analysis_limit': 5},
                    'premium': {'consultations_limit': -1, 'documents_limit': 30, 'analysis_limit': 15},
                    'corporate': {'consultations_limit': -1, 'documents_limit': 100, 'analysis_limit': 50}
                }
                limits = limits_map.get(subscription_type, limits_map['trial'])
            else:
                # Получаем лимиты из БД
                limits_result = self.client.table('subscription_limits').select('*').eq(
                    'subscription_type', subscription_type
                ).execute()
                
                if limits_result.data:
                    limits = limits_result.data[0]
                else:
                    # Дефолтные лимиты если не найдены
                    limits = {'consultations_limit': 3, 'documents_limit': 2, 'analysis_limit': 1}
            
            # Корректное формирование имени поля (analysis не нужно делать plural)
            if action_type == 'analysis':
                limit_field = "analysis_limit"
                used_field = "analysis_used"
            else:
                limit_field = f"{action_type}s_limit"
                used_field = f"{action_type}s_used"
            
            current_limit = limits.get(limit_field, 0)
            current_used = current_usage.get(used_field, 0)
            
            # Проверяем лимит (-1 = безлимит)
            if current_limit != -1 and current_used >= current_limit:
                return False, {
                    'error': 'limit_exceeded',
                    'message': f'Превышен лимит для {action_type}',
                    'used': current_used,
                    'limit': current_limit,
                    'subscription_type': status['subscription_type']
                }
            
            # Логируем использование
            usage_data = {
                'user_id': user['id'],
                'subscription_id': status.get('subscription_id'),
                'action_type': action_type,
                'details': details or {}
            }
            
            self.client.table('usage_logs').insert(usage_data).execute()
            
            # Возвращаем успех с информацией об использовании
            return True, {
                'success': True,
                'used': current_used + 1,
                'limit': current_limit,
                'subscription_type': status['subscription_type'],
                'expires_at': status['expires_at']
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки/логирования использования для {telegram_id}: {e}")
            raise

    async def get_usage_stats(self, telegram_id: int) -> Dict[str, Any]:
        """
        Получает статистику использования для пользователя
        """
        try:
            status = await self.get_user_subscription_status(telegram_id)
            
            if not status['has_subscription']:
                return {
                    'has_subscription': False,
                    'trial_used': status['is_trial_used']
                }
            
            if self.test_mode:
                # В тестовом режиме возвращаем эмулированные данные
                subscription_type = status.get('subscription_type', 'trial')
                
                # Эмулируем лимиты для разных тарифов
                limits_map = {
                    'trial': {'consultations': 3, 'documents': 2, 'analysis': 1},
                    'basic': {'consultations': 25, 'documents': 10, 'analysis': 5},
                    'premium': {'consultations': -1, 'documents': 30, 'analysis': 15},
                    'corporate': {'consultations': -1, 'documents': 100, 'analysis': 50}
                }
                
                limits = limits_map.get(subscription_type, limits_map['trial'])
                
                return {
                    'has_subscription': True,
                    'subscription_type': subscription_type,
                    'expires_at': status['expires_at'],
                    'consultations': {
                        'used': 0,
                        'limit': limits['consultations']
                    },
                    'documents': {
                        'used': 0,
                        'limit': limits['documents']
                    },
                    'analysis': {
                        'used': 0,
                        'limit': limits['analysis']
                    }
                }
            
            # Получаем лимиты из subscription_limits
            subscription_type = status['subscription_type']
            limits_result = self.client.table('subscription_limits').select('*').eq(
                'subscription_type', subscription_type
            ).execute()
            
            if not limits_result.data:
                # Если лимиты не найдены, используем дефолтные
                limits = {'consultations_limit': 3, 'documents_limit': 2, 'analysis_limit': 1}
            else:
                limits = limits_result.data[0]
            
            # Получаем использование
            user = await self.get_or_create_user(telegram_id)
            try:
                usage_result = self.client.rpc('get_current_usage', {
                    'p_user_id': user['id'],
                    'p_subscription_id': status.get('subscription_id')
                }).execute()
                
                current_usage = usage_result.data[0] if usage_result.data else {
                    'consultations_used': 0,
                    'documents_used': 0,
                    'analysis_used': 0
                }
            except:
                # Если функция не найдена, используем нули
                current_usage = {
                    'consultations_used': 0,
                    'documents_used': 0,
                    'analysis_used': 0
                }
            
            return {
                'has_subscription': True,
                'subscription_type': subscription_type,
                'expires_at': status['expires_at'],
                'consultations': {
                    'used': current_usage['consultations_used'],
                    'limit': limits['consultations_limit']
                },
                'documents': {
                    'used': current_usage['documents_used'],
                    'limit': limits['documents_limit']
                },
                'analysis': {
                    'used': current_usage['analysis_used'],
                    'limit': limits['analysis_limit']
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики для {telegram_id}: {e}")
            raise

    # === УПРАВЛЕНИЕ ПЛАТЕЖАМИ ===

    async def create_payment_record(self, telegram_id: int, subscription_type: str,
                                  yookassa_payment_id: str, amount_kopecks: int,
                                  payment_url: str) -> Dict[str, Any]:
        """
        Создает запись о платеже
        """
        try:
            user = await self.get_or_create_user(telegram_id)
            
            if self.test_mode:
                # В тестовом режиме просто логируем и возвращаем эмуляцию
                payment = {
                    'id': f'test_payment_{yookassa_payment_id}',
                    'user_id': user['id'],
                    'yookassa_payment_id': yookassa_payment_id,
                    'amount_kopecks': amount_kopecks,
                    'status': 'pending',
                    'payment_url': payment_url,
                    'created_at': datetime.now().isoformat()
                }
                logger.info(f"[TEST] Создана запись о платеже {yookassa_payment_id} для пользователя {telegram_id}")
                return payment
            
            payment_data = {
                'user_id': user['id'],
                'yookassa_payment_id': yookassa_payment_id,
                'amount_kopecks': amount_kopecks,
                'status': 'pending',
                'payment_url': payment_url
            }
            
            result = self.client.table('payments').insert(payment_data).execute()
            payment = result.data[0]
            
            logger.info(f"Создана запись о платеже {yookassa_payment_id} для пользователя {telegram_id}")
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка создания записи о платеже для {telegram_id}: {e}")
            raise

    async def update_payment_status(self, yookassa_payment_id: str, status: str) -> Dict[str, Any]:
        """
        Обновляет статус платежа
        """
        try:
            if self.test_mode:
                # В тестовом режиме просто логируем
                logger.info(f"[TEST] Обновлен статус платежа {yookassa_payment_id}: {status}")
                return {
                    'id': f'test_payment_{yookassa_payment_id}',
                    'yookassa_payment_id': yookassa_payment_id,
                    'status': status
                }
            
            result = self.client.table('payments').update({
                'status': status
            }).eq('yookassa_payment_id', yookassa_payment_id).execute()
            
            if result.data:
                payment = result.data[0]
                logger.info(f"Обновлен статус платежа {yookassa_payment_id}: {status}")
                return payment
            else:
                logger.warning(f"Платеж {yookassa_payment_id} не найден")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа {yookassa_payment_id}: {e}")
            raise


# Глобальный экземпляр клиента
supabase_client = SupabaseClient() 