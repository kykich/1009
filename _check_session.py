#!/usr/bin/env python
"""Тест: проверяем запись и чтение session.json."""
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Прочитаем session.json
with open('session/session.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

s = d['compact']['summary']
print('Type:', type(s))
print('Repr:', repr(s[:100]))

# Проверим байты в файле
with open('session/session.json', 'rb') as f:
    content = f.read()

# Найдем summary
idx = content.find(b'"summary"')
if idx >= 0:
    # Найдем начало строки
    start = content.index(b'"', idx + 9) + 1
    end = content.index(b'"', start)
    raw = content[start:end]
    print('Raw bytes in file:', raw[:100])
    print('Hex:', raw[:100].hex())
    
    # Попробуем декодировать как UTF-8
    try:
        decoded = raw.decode('utf-8')
        print('Decoded UTF-8:', decoded[:100])
    except:
        print('Cannot decode as UTF-8')
        
    # Попробуем как cp1251
    try:
        decoded = raw.decode('cp1251')
        print('Decoded cp1251:', decoded[:100])
    except:
        print('Cannot decode as cp1251')
