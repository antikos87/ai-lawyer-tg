#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пакет для работы с Supabase
"""

from .database import SupabaseClient

# Создаем экземпляр клиента для импорта
supabase_client = SupabaseClient()
 
__version__ = "1.0.0" 