"""Kostenlose Chat-Modelle über OpenAI-kompatible APIs (Cerebras, GitHub Models).

Anders als die Managed Agents haben diese Modelle keine Websuche und keinen
serverseitigen Verlauf. Der Bot speichert den Verlauf daher selbst (gekürzt) in `state/`.
Anbieter werden der Reihe nach probiert: Fällt einer aus (Rate-Limit, Serverfehler,
ungültiger Key, keine Verbindung), übernimmt der nächste.
"""

import logging
from dataclasses import dataclass
from importlib.resources import files

import httpx

from snow_bot.state import JsonStore

log = logging.getLogger(__name__)

# Wie viele Nachrichten (Snow + Bot) pro Chat behalten werden.
MAX_HISTORY = 20


@dataclass(frozen=True)
class Provider:
    name: str  # Anzeigename, z. B. "Cerebras"
    base_url: str  # ohne /chat/completions
    api_key: str
    model: str

    def __repr__(self) -> str:  # Key nie in Logs oder Tracebacks
        return f"Provider(name={self.name!r}, model={self.model!r})"


class FreeLLMError(RuntimeError):
    """Kein Anbieter konnte antworten."""


@dataclass
class FreeAnswer:
    text: str
    provider: str
    model: str


def system_prompt() -> str:
    return files("snow_bot.prompts").joinpath("snow-free.md").read_text(encoding="utf-8")


def _grund(fehler: Exception) -> str:
    """Kurzer Grund für Logs, ohne Header oder Keys."""
    if isinstance(fehler, httpx.HTTPStatusError):
        return f"HTTP {fehler.response.status_code}"
    return type(fehler).__name__


class FreeChat:
    def __init__(
        self,
        providers: list[Provider],
        store: JsonStore,
        client: httpx.Client | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.providers = providers
        self.store = store
        self.client = client or httpx.Client(timeout=timeout)

    @property
    def available(self) -> bool:
        return bool(self.providers)

    def describe(self) -> str:
        return " → ".join(f"{p.name} ({p.model})" for p in self.providers) or "nicht eingerichtet"

    # Verlauf ---------------------------------------------------------------

    def history(self, chat_id: int) -> list[dict]:
        return self.store.load().get(str(chat_id), [])

    def reset(self, chat_id: int) -> None:
        data = self.store.load()
        data.pop(str(chat_id), None)
        self.store.save(data)

    def _remember(self, chat_id: int, user_text: str, answer: str) -> None:
        data = self.store.load()
        verlauf = data.get(str(chat_id), [])
        verlauf += [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ]
        data[str(chat_id)] = verlauf[-MAX_HISTORY:]
        self.store.save(data)

    # Anfrage ---------------------------------------------------------------

    def _ask(self, provider: Provider, messages: list[dict]) -> str:
        antwort = self.client.post(
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json={"model": provider.model, "messages": messages},
        )
        antwort.raise_for_status()
        inhalt = antwort.json()["choices"][0]["message"].get("content") or ""
        return inhalt.strip()

    def chat(self, chat_id: int, text: str) -> FreeAnswer:
        if not self.providers:
            raise FreeLLMError("Kein Gratis-Anbieter eingerichtet (Keys in .env fehlen).")
        messages = [
            {"role": "system", "content": system_prompt()},
            *self.history(chat_id),
            {"role": "user", "content": text},
        ]
        gruende: list[str] = []
        for provider in self.providers:
            try:
                inhalt = self._ask(provider, messages)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as fehler:
                grund = _grund(fehler)
                log.warning("%s fehlgeschlagen: %s", provider.name, grund)
                gruende.append(f"{provider.name}: {grund}")
                continue
            if not inhalt:
                gruende.append(f"{provider.name}: leere Antwort")
                continue
            self._remember(chat_id, text, inhalt)
            return FreeAnswer(text=inhalt, provider=provider.name, model=provider.model)
        raise FreeLLMError("Alle Gratis-Anbieter sind ausgefallen (" + "; ".join(gruende) + ").")
