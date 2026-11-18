from types import SimpleNamespace as NS

from snow_bot.runner import collect


class FakeEvents:
    def __init__(self):
        self.sent = []

    def send(self, session_id, events):
        self.sent.append((session_id, events))


class FakeClient:
    def __init__(self):
        self.events = FakeEvents()
        self.beta = NS(sessions=NS(events=self.events))


def text(t):
    return NS(type="text", text=t)


def msg(*texts):
    return NS(type="agent.message", content=[text(t) for t in texts])


def idle(reason):
    return NS(type="session.status_idle", stop_reason=NS(type=reason))


def test_sammelt_text_bis_end_turn():
    events = [msg("Hallo"), NS(type="agent.thinking"), msg("Welt"), idle("end_turn"), msg("danach")]
    r = collect(FakeClient(), "s", iter(events))
    assert r.text == "Hallo\n\nWelt"
    assert r.stop == "end_turn"


def test_requires_action_wird_abgelehnt_und_weiter_gehoert():
    c = FakeClient()
    ask = NS(type="agent.tool_use", id="sevt_1", evaluated_permission="ask")
    events = [ask, idle("requires_action"), msg("ok"), idle("end_turn")]
    r = collect(c, "s1", iter(events))
    assert r.text == "ok"
    (sid, sent), = c.events.sent
    assert sid == "s1"
    assert sent[0]["type"] == "user.tool_confirmation"
    assert sent[0]["tool_use_id"] == "sevt_1"
    assert sent[0]["result"] == "deny"


def test_erlaubter_tool_call_wird_nicht_beantwortet():
    c = FakeClient()
    events = [NS(type="agent.tool_use", id="x", evaluated_permission="allow"), idle("end_turn")]
    collect(c, "s", iter(events))
    assert c.events.sent == []


def test_budget_und_fehler():
    err = NS(type="session.error", error=NS(message="kaputt"))
    r = collect(FakeClient(), "s", iter([msg("Teil"), err, idle("budget_reached")]))
    assert r.stop == "budget_reached"
    assert r.errors == ["kaputt"]
    assert r.text == "Teil"


def test_terminiert():
    r = collect(FakeClient(), "s", iter([NS(type="session.status_terminated")]))
    assert r.stop == "error"
