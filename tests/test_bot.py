from snow_bot.bot import describe, split_message
from snow_bot.runner import TurnResult


def test_kurze_nachricht_bleibt_ganz():
    assert split_message("abc") == ["abc"]


def test_teilt_an_absaetzen_und_haelt_limit():
    text = ("a" * 30 + "\n\n") * 10
    teile = split_message(text, limit=70)
    assert all(len(t) <= 70 for t in teile)
    assert "".join(teile).replace("\n", "") == "a" * 300


def test_harter_schnitt_ohne_umbruch():
    teile = split_message("x" * 250, limit=100)
    assert [len(t) for t in teile] == [100, 100, 50]


def test_budget_hinweis():
    t = describe(TurnResult(text="Antwort", stop="budget_reached"), "250")
    assert "Antwort" in t and "$2.50" in t and "/neu" in t


def test_leere_antwort():
    assert describe(TurnResult(), "200") == "(Keine Antwort erhalten.)"


def test_build_mit_wartezeiten(tmp_path, monkeypatch):
    from snow_bot.bot import POLL_TIMEOUT, SnowBot
    from snow_bot.config import Config
    from snow_bot.free_llm import Provider

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = Provider("Cerebras", "https://x.test/v1", "k", "m")
    config = Config("123:abc", 1, tmp_path, "200", (provider,))
    app = SnowBot(config).build()
    assert app.bot.request._client.timeout.read == 30  # normale Anfragen
    assert app.updater.bot._request[0]._client.timeout.read == 40 > POLL_TIMEOUT
