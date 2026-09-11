"""
Хранилище сессии диалога на диске (JSON в папке session/).

Диалог ведётся на сервере и периодически/поэтапно сохраняется в файл
session/session.json. При запуске сервера хранилище подхватывает ранее
сохранённую историю (если она есть), тем самым сохраняя непрерывность
беседы между запусками.

Структура файла:
{
  "updated": "ISO-время последнего сохранения",
  "count":   число сообщений,
  "messages":[ ... элементы диалога ... ],
  "compact": {
    "enabled": false,      // включено ли сжатие
    "keep": 10,            // сколько последних сообщений хранить полностью
    "summary": ""          // сжатое содержание ранней части истории
  }
}

Элемент диалога (один ход):
  - пользователь: {"role": "user",  "content": "текст вопроса"}
  - ассистент:    {"role": "assistant", "content": "текст-конкат ответов",
                   "html": "готовая HTML-разметка ответа",
                   "answers": [{"label": "…", model/text…}, …]}
"""
import json
import os
import threading
import time

from . import config

__all__ = ["SessionStore"]


class SessionStore:
    """Потокобезопасное хранилище одного активного диалога в JSON-файле."""

    def __init__(self, path=None):
        self.path = path or config.SESSION_FILE
        self.lock = threading.RLock()
        self.messages = []
        self.compact = {
            "enabled": False,
            "keep": config.COMPACT_KEEP,
            "summary": "",
        }
        self.load()

    # ---- чтение ----
    def load(self):
        """Читает сохранённую историю из файла (None/нет файла -> пустая)."""
        with self.lock:
            self.messages = []
            self.compact = {
                "enabled": False,
                "keep": config.COMPACT_KEEP,
                "summary": "",
            }
            if not self.path or not os.path.isfile(self.path):
                return
            try:
                with open(self.path, encoding="utf-8") as fh:
                    data = json.load(fh)
                msgs = data.get("messages") if isinstance(data, dict) else None
                if isinstance(msgs, list):
                    # оставляем только корректные элементы диалога
                    self.messages = [m for m in msgs
                                     if isinstance(m, dict)
                                     and m.get("role") in ("user", "assistant")]
                # Загружаем настройки сжатия
                compact = data.get("compact")
                if isinstance(compact, dict):
                    self.compact["enabled"] = bool(compact.get("enabled", False))
                    self.compact["keep"] = int(compact.get("keep", config.COMPACT_KEEP))
                    self.compact["summary"] = str(compact.get("summary", ""))
            except Exception:
                # Битый файл не должен ронять сервер — стартуем с чистой истрии
                self.messages = []

    def snapshot(self):
        """Копия списка сообщений текущей сессии."""
        with self.lock:
            return list(self.messages)

    def snapshot_full(self):
        """Полная копия сессии: сообщения + настройки сжатия."""
        with self.lock:
            return {
                "messages": list(self.messages),
                "compact": dict(self.compact),
            }

    def has_history(self):
        """True, если в сессии уже есть сохранённый диалог."""
        with self.lock:
            return bool(self.messages)

    # ---- запись ----
    def append_turn(self, question, assistant_entry):
        """Добавляет в историю ход «вопрос -> ответ(ы)» и сохраняет на диск."""
        with self.lock:
            self.messages.append({"role": "user", "content": str(question)})
            entry = dict(assistant_entry or {})
            entry.setdefault("role", "assistant")
            self.messages.append(entry)
            self._save_locked()

    def save(self):
        """Принудительное сохранение текущего состояния на диск."""
        with self.lock:
            self._save_locked()

    def _save_locked(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {
            "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(self.messages),
            "messages": self.messages,
            "compact": self.compact,
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception as exc:                    # не роняем запрос из-за диска
            print("[session] не удалось сохранить сессию: %s" % exc, flush=True)

    # ---- сброс ----
    def reset(self):
        """Очищает сессию: начинает новый разговор с чистого листа."""
        with self.lock:
            self.messages = []
            self.compact = {
                "enabled": False,
                "keep": config.COMPACT_KEEP,
                "summary": "",
            }
            self._save_locked()

    # ---- Настройки сжатия ----

    def set_compact(self, enabled, keep=None, summary=None):
        """Обновляет настройки сжатия и сохраняет на диск."""
        with self.lock:
            if enabled is not None:
                self.compact["enabled"] = bool(enabled)
            if keep is not None:
                self.compact["keep"] = int(keep)
            if summary is not None:
                self.compact["summary"] = str(summary)
            self._save_locked()

    def get_compact(self):
        """Возвращает текущие настройки сжатия (копия)."""
        with self.lock:
            return dict(self.compact)

    def get_compacted_messages(self):
        """Возвращает историю с применённым сжатием.

        Если сжатие включено и есть summary:
          - последние N сообщений (keep) возвращаются полностью
          - предыдущие заменяются на {"role": "system", "content": summary}
        Если сжатие выключено:
          - возвращаются все сообщения как есть
        """
        with self.lock:
            if not self.compact["enabled"] or not self.compact["summary"]:
                return list(self.messages)
            keep = max(0, self.compact["keep"])
            if keep >= len(self.messages):
                return list(self.messages)
            # Берём последние keep сообщений
            recent = list(self.messages[-keep:]) if keep > 0 else []
            # Добавляем summary как системное сообщение
            summary_msg = {
                "role": "system",
                "content": self.compact["summary"],
            }
            return [summary_msg] + recent
