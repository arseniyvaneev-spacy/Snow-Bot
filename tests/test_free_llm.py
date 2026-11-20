import json

import anthropic
import httpx
import pytest

from snow_bot.bot import describe_free
from snow_bot.config import free_providers
from snow_bot.errors import fallback_sinnvoll
from snow_bot.free_llm import MAX_HISTORY, FreeAnswer, FreeChat, FreeLLMError, Provider
from snow_bot.state import JsonStore

CEREBRAS = Provider("Cerebras", "https://cerebras.test/v1", "key-c", "gpt-oss-120b")
GITHUB = Provider("GitHub Models", "https://github.test/inference", "key-g", "openai/x")


def ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def make_chat(tmp_path, handler, providers=(CEREBRAS, GITHUB)) -> tuple[FreeChat, list]:
    calls: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(wrapped))
    store = JsonStore(tmp_path / "free_history.json")
    return FreeChat(list(providers), store, client=client), calls


def test_erster_anbieter_antwortet(tmp_path):
    chat, calls = make_chat(tmp_path, lambda r: ok("\n\nHallo"))
    antwort = chat.chat(1, "Hi")
    assert (antwort.text, antwort.provider) == ("Hallo", "Cerebras")
    assert len(calls) == 1
    req = calls[0]
    assert str(req.url) == "https://cerebras.test/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer key-c"
    body = json.loads(req.content)
    assert body["model"] == "gpt-oss-120b"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][-1] == {"role": "user", "content": "Hi"}


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_fallback_auf_github(tmp_path, status):
    def handler(r):
        if "cerebras" in r.url.host:
            return httpx.Response(status, json={"error": "x"})
        return ok("von GitHub")

    chat, calls = make_chat(tmp_path, handler)
    antwort = chat.chat(1, "Hi")
    assert antwort.provider == "GitHub Models"
    assert len(calls) == 2


def test_verbindungsfehler_und_leere_antwort(tmp_path):
    def handler(r):
        if "cerebras" in r.url.host:
            raise httpx.ConnectError("weg")
        return ok("  ")

    chat, _ = make_chat(tmp_path, handler)
    with pytest.raises(FreeLLMError) as info:
        chat.chat(1, "Hi")
    meldung = str(info.value)
    assert "Cerebras: ConnectError" in meldung and "leere Antwort" in meldung
    assert "key-" not in meldung
    assert chat.history(1) == []  # Fehlschläge landen nicht im Verlauf


def test_verlauf_wird_mitgeschickt_gekuerzt_und_geloescht(tmp_path):
    chat, calls = make_chat(tmp_path, lambda r: ok("A"))
    for i in range(MAX_HISTORY):
        chat.chat(7, f"Frage {i}")
    assert len(chat.history(7)) == MAX_HISTORY
    assert chat.history(7)[-2] == {"role": "user", "content": f"Frage {MAX_HISTORY - 1}"}
    letzte = json.loads(calls[-1].content)["messages"]
    assert len(letzte) == 1 + MAX_HISTORY + 1  # System + gekürzter Verlauf + neue Frage
    assert chat.history(8) == []  # andere Chats getrennt
    chat.reset(7)
    assert chat.history(7) == []


def test_ohne_anbieter(tmp_path):
    chat, _ = make_chat(tmp_path, lambda r: ok("x"), providers=())
    assert not chat.available
    with pytest.raises(FreeLLMError):
        chat.chat(1, "Hi")


def test_key_nicht_im_repr():
    assert "key-c" not in repr(CEREBRAS)


def test_config_liest_keys(monkeypatch):
    for var in ("CEREBRAS_API_KEY", "CEREBRAS_MODEL", "GITHUB_MODELS_TOKEN", "GITHUB_MODELS_MODEL"):
        monkeypatch.delenv(var, raising=False)
    assert free_providers() == ()
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", " tok ")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk")
    monkeypatch.setenv("CEREBRAS_MODEL", "qwen-3.8-27b")
    namen = [(p.name, p.model, p.api_key) for p in free_providers()]
    assert namen == [
        ("Cerebras", "qwen-3.8-27b", "csk"),
        ("GitHub Models", "openai/gpt-4.1-mini", "tok"),
    ]


def _status_fehler(cls, status: int, message: str = "x"):
    request = httpx.Request("POST", "https://api.anthropic.com")
    return cls(message, response=httpx.Response(status, request=request), body=None)


def test_fallback_nur_bei_ausfall():
    assert fallback_sinnvoll(_status_fehler(anthropic.RateLimitError, 429))
    assert fallback_sinnvoll(_status_fehler(anthropic.OverloadedError, 529))
    assert fallback_sinnvoll(_status_fehler(anthropic.AuthenticationError, 401))
    assert fallback_sinnvoll(
        _status_fehler(anthropic.BadRequestError, 400, "Your credit balance is too low")
    )
    assert fallback_sinnvoll(anthropic.APIConnectionError(request=httpx.Request("GET", "https://x")))
    assert not fallback_sinnvoll(_status_fehler(anthropic.BadRequestError, 400, "bad param"))
    assert not fallback_sinnvoll(_status_fehler(anthropic.NotFoundError, 404))


def test_describe_free():
    a = FreeAnswer("Text", "Cerebras", "gpt-oss-120b")
    assert describe_free(a) == "Text"
    assert "GitHub Models" in describe_free(FreeAnswer("T", "GitHub Models", "m"))
    t = describe_free(a, fallback_grund="Kein Guthaben.")
    assert "Kein Guthaben." in t and "ohne Websuche" in t
