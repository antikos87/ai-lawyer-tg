#!/usr/bin/env python3
import subprocess
import os

# Переходим в директорию проекта
os.chdir('/home/aibot/projects/ai-lawyer-tg')

try:
    # Добавляем все изменения
    result = subprocess.run(['git', 'add', '.'], capture_output=True, text=True)
    print(f"git add: {result.returncode}")
    if result.stderr:
        print(f"stderr: {result.stderr}")
    
    # Делаем коммит
    commit_message = """Fix: Исправлены ошибки с переменной text и кнопками навигации

- Исправлена ошибка NameError с переменной text в handle_document_upload
- Убрано обращение к несуществующему полю description в back_to_subtypes
- Все кнопки навигации в создании документов теперь работают корректно
- PDF анализ работает без ошибок"""
    
    result = subprocess.run(['git', 'commit', '-m', commit_message], capture_output=True, text=True)
    print(f"git commit: {result.returncode}")
    print(f"stdout: {result.stdout}")
    if result.stderr:
        print(f"stderr: {result.stderr}")
    
    # Проверяем статус
    result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
    print(f"git status: {result.returncode}")
    print(f"status: {result.stdout}")
    
    # Показываем последние коммиты
    result = subprocess.run(['git', 'log', '--oneline', '-3'], capture_output=True, text=True)
    print(f"git log: {result.returncode}")
    print(f"log: {result.stdout}")
    
except Exception as e:
    print(f"Ошибка: {e}") 