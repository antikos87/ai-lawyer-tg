#!/bin/bash
cd /home/aibot/projects/ai-lawyer-tg
git add .
git commit -m "Fix: Исправлены ошибки с переменной text и кнопками навигации

- Исправлена ошибка NameError с переменной text в handle_document_upload
- Убрано обращение к несуществующему полю description в back_to_subtypes  
- Все кнопки навигации в создании документов теперь работают корректно
- PDF анализ работает без ошибок"
git status
echo "Коммит завершен!" 