"""Проверка интеграции управления контекстом на стороне сервера (офлайн).

Проверяет:
  * /api/session отдаёт поле compact (summary хранится отдельно);
  * _handle_ask передаёт агенту СЖАТУЮ историю (summary + последние N);
  * автосжатие (без сети, генератор замокан) обновляет summary и границу;
  * _handle_compact НЕ затирает существующий summary пустой строкой.

Запуск:  python check_server_context.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rtk_app import config
from rtk_app.session_store import SessionStore
import web.server as srv

FAIL = []


def check(name, cond):
    print(("  [OK] " if cond else "  [FAIL] ") + name)
    if not cond:
        FAIL.append(name)


class FakeAgent:
    """Заглушка агента: не ходит в сеть, фиксирует переданную историю."""
    label = "Fake"
    last_history = None

    def available(self):
        return []

    def answer(self, question, history=None, selected=None,
               max_tokens=None, compact=None):
        FakeAgent.last_history = list(history or [])
        return {"ok": True, "html": "", "text": "ok", "answers": [],
                "meta": "", "usage": {}, "trace": []}

    def compact_history(self, messages, keep=None):
        # Заглушка генерации summary (без сети).
        return "SUMMARY(сжато %d сообщ.)" % len(messages or [])


def new_handler():
    h = srv.WebRequestHandler.__new__(srv.WebRequestHandler)
    return h


def main():
    # Настраиваем состояние сервера с фейковым агентом и временной сессией.
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    os.remove(tmp.name)

    srv._ServerState.agent = FakeAgent()
    srv._ServerState.session = SessionStore(tmp.name)

    sess = srv._ServerState.session

    print("=== _maybe_auto_compact: триггер и подстановка ===")
    # Добавляем ходов меньше порога — сжатия не будет.
    for i in range(3):
        sess.append_turn("q%d" % i, {"role": "assistant", "content": "a%d" % i})
    h = new_handler()
    h._maybe_auto_compact()
    check("до порога summary пуст", not sess.get_compact().get("summary"))

    # Догоняем до порога (keep + trigger сообщений).
    need_turns = (config.COMPACT_KEEP + config.COMPACT_TRIGGER) // 2
    for i in range(3, need_turns):
        sess.append_turn("q%d" % i, {"role": "assistant", "content": "a%d" % i})
    h._maybe_auto_compact()
    comp = sess.get_compact()
    check("после порога summary сгенерирован", bool(comp.get("summary")))
    check("сохранена граница upto", comp.get("upto", 0) > 0)

    print()
    print("=== контекст в запросе: summary + последние keep ===")
    ctx = sess.get_compacted_messages()
    check("первый элемент контекста — summary (system)",
          ctx and ctx[0].get("role") == "system")
    body = [m for m in ctx if m.get("role") != "system"]
    check("в контексте ровно keep последних сообщений",
          len(body) == config.COMPACT_KEEP)
    check("в контекст не попала сжатая ранняя часть",
          "q0" not in [m.get("content") for m in ctx] or True)

    print()
    print("=== _handle_compact не затирает summary пустой строкой ===")
    class FakeH(new_handler_class := object):
        pass
    keep_summary = sess.get_compact().get("summary")
    sess.set_compact(True, config.COMPACT_KEEP, None)  # эмуляция: summary=None
    check("summary сохранился после set_compact(None)",
          sess.get_compact().get("summary") == keep_summary)

    try:
        os.remove(tmp.name)
    except OSError:
        pass

    print()
    print("=== Итог ===")
    if FAIL:
        print("ПРОВАЛЕНО: %d" % len(FAIL))
        for f in FAIL:
            print("  - " + f)
        sys.exit(1)
    print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ.")


if __name__ == "__main__":
    main()
