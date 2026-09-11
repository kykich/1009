#!/usr/bin/env python
"""Тест: проверяем что GigaChat возвращает корректный UTF-8."""
import json
import sys

# Принудительно устанавливаем UTF-8 для вывода
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from rtk_app import gigachat, config

# Прочитаем ключ
with open(config.GC_KEY_FILE, 'r', encoding='utf-8') as f:
    key = None
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            key = line
            break

if not key:
    print("No key found")
    sys.exit(1)

# Протестируем запрос
messages = [
    {"role": "system", "content": "Ты ассистент. Отвечай кратко."},
    {"role": "user", "content": "Привет. Напиши привет на русском."},
]

try:
    result = gigachat.chat(messages, temperature=0.3)
    content = result.get('content', '')
    
    print('Content type:', type(content))
    print('Content repr:', repr(content[:100]))
    
    # Запишем в файл
    with open('_gigachat_test.txt', 'w', encoding='utf-8-sig') as f:
        f.write(content)
    print('Written to _gigachat_test.txt')
    
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
