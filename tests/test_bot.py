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
