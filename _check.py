#!/usr/bin/env python
import json
import sys

# Принудительно устанавливаем UTF-8 для вывода
sys.stdout.reconfigure(encoding='utf-8')

with open('session/session.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

s = d['compact']['summary']
print('Summary length:', len(s))
print('Summary (first 150 chars):')
print(s[:150])

# Also write to a file with BOM for Windows Notepad
with open('_summary_check.txt', 'w', encoding='utf-8-sig') as f:
    f.write(s)
print('Written to _summary_check.txt')
