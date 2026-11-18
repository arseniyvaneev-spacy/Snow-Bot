"""Kleine JSON-Ablage für Agent-IDs und laufende Sitzungen."""

import json
import os
import tempfile
from pathlib import Path


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomar schreiben: erst Temp-Datei, dann umbenennen.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)


class SessionStore:
    """Pro Telegram-Chat: welcher Agent aktiv ist und welche Session pro Agent läuft."""

    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def _chat(self, data: dict, chat_id: int) -> dict:
        return data.setdefault(str(chat_id), {"active": "snow", "sessions": {}})

    def active_agent(self, chat_id: int) -> str:
        return self._chat(self.store.load(), chat_id)["active"]

    def set_active(self, chat_id: int, agent_key: str) -> None:
        data = self.store.load()
        self._chat(data, chat_id)["active"] = agent_key
        self.store.save(data)

    def session_id(self, chat_id: int, agent_key: str) -> str | None:
        return self._chat(self.store.load(), chat_id)["sessions"].get(agent_key)

    def set_session(self, chat_id: int, agent_key: str, session_id: str) -> None:
        data = self.store.load()
        self._chat(data, chat_id)["sessions"][agent_key] = session_id
        self.store.save(data)

    def forget_session(self, chat_id: int, agent_key: str) -> None:
        data = self.store.load()
        self._chat(data, chat_id)["sessions"].pop(agent_key, None)
        self.store.save(data)
