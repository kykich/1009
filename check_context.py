"""Проверка механизма управления контекстом (офлайн, без сети).

Проверяет три требования:
  1) последние N сообщений хранятся/передаются «как есть»;
  2) вытесняемая часть заменяется summary (триггер каждые COMPACT_TRIGGER);
  3) summary хранится ОТДЕЛЬНО и подставляется в запрос вместо истории.

Запуск:  python check_context.py
"""
import json
import os
import tempfile
import sys

# Гарантируем импорт пакета из корня проекта.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rtk_app import config
from rtk_app.session_store import SessionStore

FAIL = []


def check(name, cond):
    print(("  [OK] " if cond else "  [FAIL] ") + name)
    if not cond:
        FAIL.append(name)


def make_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    os.remove(tmp.name)          # пусть SessionStore сам создаст файл
    return SessionStore(tmp.name), tmp.name


def add_turns(store, n, text="вопрос"):
    """Добавляет n ходов (каждый ход = user + assistant)."""
    for i in range(n):
        store.append_turn("%s %d" % (text, i), {
            "role": "assistant",
            "content": "ответ %d" % i,
        })


def main():
    print("=== Требование 1: последние N сообщений хранятся «как есть» ===")
    store, path = make_store()
    add_turns(store, 8)                      # 16 сообщений
    keep = config.COMPACT_KEEP
    store.apply_summary("SUMMARY: ранняя часть диалога.", upto=6, keep=keep)
    ctx = store.get_compacted_messages()
    # Должно быть: 1 system-summary + последние keep сообщений
    body = [m for m in ctx if m.get("role") != "system"]
    check("контекст = summary + последние %d сообщений" % keep,
          len(body) == keep)
    full = store.snapshot()
    check("последние N совпадают с хвостом полной истории",
          [m["content"] for m in body] ==
          [m["content"] for m in full[-keep:]])
    check("summary подставлен первым (role=system)",
          ctx and ctx[0].get("role") == "system"
          and "SUMMARY" in ctx[0].get("content", ""))

    print()
    print("=== Требование 2: вытесняемую часть заменяет summary ===")
    store2, path2 = make_store()
    keep2 = config.COMPACT_KEEP
    add_turns(store2, (keep2 + config.COMPACT_TRIGGER) // 2)
    n_msgs = len(store2.snapshot())
    head, end = store2.head_to_compact()
    check("вытесняемая часть = всё, кроме последних keep",
          end == n_msgs - keep2)
    check("срабатывает триггер автосжатия (>=%d)" % config.COMPACT_TRIGGER,
          store2.should_auto_compact())
    # до порога автосжатие не срабатывает
    store3, path3 = make_store()
    add_turns(store3, 2)
    check("до порога автосжатие НЕ срабатывает",
          not store3.should_auto_compact())

    print()
    print("=== Требование 3: summary хранится отдельно и подставляется ===")
    data = json.load(open(path, encoding="utf-8"))
    check("summary хранится отдельно (поле compact.summary)",
          isinstance(data.get("compact"), dict)
          and data["compact"].get("summary"))
    check("граница покрытия сохранена (compact.upto)",
          data["compact"].get("upto") == 6)
    check("полная история тоже сохранена (messages)",
          isinstance(data.get("messages"), list)
          and len(data["messages"]) == 16)
    # summary НЕ должен попадать в messages (он хранится отдельно)
    check("summary отсутствует среди messages",
          all("SUMMARY" not in str(m.get("content", ""))
              for m in data["messages"]))

    # Перезагрузка с диска сохраняет summary и сжатие
    store_reload = SessionStore(path)
    ctx2 = store_reload.get_compacted_messages()
    check("после перезагрузки с диска контекст остаётся сжатым",
          ctx2 and ctx2[0].get("role") == "system"
          and "SUMMARY" in ctx2[0].get("content", ""))

    print()
    for p in (path, path2, path3):
        try:
            os.remove(p)
        except OSError:
            pass

    print("=== Итог ===")
    if FAIL:
        print("ПРОВАЛЕНО проверок: %d" % len(FAIL))
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ.")


if __name__ == "__main__":
    main()
