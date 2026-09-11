# -*- coding: utf-8 -*-
import json

with open('session/session.json', 'rb') as f:
    data = f.read()

idx = data.find(b'"summary"')
if idx > 0:
    start = data.index(b'"', idx + 9) + 1
    end = data.index(b'"', start)
    raw = data[start:end]
    print('Raw bytes:', raw)
    print('UTF-8 decoded:', raw.decode('utf-8'))
