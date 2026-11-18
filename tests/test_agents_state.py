from snow_bot.agents import SPECS, TEACHER_DOMAINS
from snow_bot.state import JsonStore, SessionStore


def test_nur_web_werkzeuge_aktiv():
    for spec in SPECS.values():
        (toolset,) = spec.tools()
        assert toolset["default_config"] == {"enabled": False}
        assert {c["name"] for c in toolset["configs"]} == {"web_search", "web_fetch"}
        assert all(c["enabled"] for c in toolset["configs"])


def test_teacher_ist_auf_doku_beschraenkt():
    spec = SPECS["teacher"]
    for c in spec.tools()[0]["configs"]:
        assert c["allowed_domains"] == TEACHER_DOMAINS
    net = spec.environment["config"]["networking"]
    assert net["type"] == "limited"
    assert "code.claude.com" in net["allowed_hosts"]


def test_snow_ist_offen():
    assert all("allowed_domains" not in c for c in SPECS["snow"].tools()[0]["configs"])


def test_prompts_laden():
    for spec in SPECS.values():
        assert "Telegram" in spec.system_prompt()


def test_session_store(tmp_path):
    s = SessionStore(JsonStore(tmp_path / "sessions.json"))
    assert s.active_agent(1) == "snow"
    s.set_active(1, "teacher")
    s.set_session(1, "teacher", "sesn_1")
    assert s.active_agent(1) == "teacher"
    assert s.session_id(1, "teacher") == "sesn_1"
    assert s.session_id(1, "snow") is None
    s.forget_session(1, "teacher")
    assert s.session_id(1, "teacher") is None
    assert s.active_agent(2) == "snow"  # andere Chats unberührt
