import pytest

from snow_bot.config import ConfigError, load, load_env_file

KEYS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_ID", "ANTHROPIC_API_KEY",
        "SESSION_BUDGET_CENTS", "SNOW_BOT_STATE_DIR"]


@pytest.fixture(autouse=True)
def leere_umgebung(monkeypatch, tmp_path):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)


def schreibe_env(tmp_path, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")


def test_laedt_env_aus_aktuellem_ordner(tmp_path):
    schreibe_env(tmp_path, "TELEGRAM_BOT_TOKEN=123:abc\nTELEGRAM_ALLOWED_USER_ID=42\n"
                           "ANTHROPIC_API_KEY=sk-test\n")
    cfg = load()
    assert cfg.telegram_token == "123:abc"
    assert cfg.allowed_user_id == 42
    assert cfg.session_budget_cents == "200"


def test_terminal_wert_gewinnt(tmp_path, monkeypatch):
    schreibe_env(tmp_path, "TELEGRAM_BOT_TOKEN=aus-datei\nTELEGRAM_ALLOWED_USER_ID=1\n"
                           "ANTHROPIC_API_KEY=k\n")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "aus-terminal")
    assert load().telegram_token == "aus-terminal"


def test_dollar_wird_nicht_ausgewertet(tmp_path):
    schreibe_env(tmp_path, "TELEGRAM_BOT_TOKEN=a$HOME${X}b\nTELEGRAM_ALLOWED_USER_ID=1\n"
                           "ANTHROPIC_API_KEY=k\n")
    assert load().telegram_token == "a$HOME${X}b"


def test_fehlende_datei_ist_kein_fehler():
    assert load_env_file() is False


def test_fehlender_wert_meldet_env(tmp_path):
    schreibe_env(tmp_path, "TELEGRAM_ALLOWED_USER_ID=1\nANTHROPIC_API_KEY=k\n")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN fehlt.*\\.env"):
        load()


def test_windows_zeilenenden(tmp_path):
    (tmp_path / ".env").write_bytes(b"TELEGRAM_BOT_TOKEN=t\r\nTELEGRAM_ALLOWED_USER_ID=7\r\n"
                                    b"ANTHROPIC_API_KEY=k\r\n")
    cfg = load()
    assert cfg.telegram_token == "t" and cfg.allowed_user_id == 7
