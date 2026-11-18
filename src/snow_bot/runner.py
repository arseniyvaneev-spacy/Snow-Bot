"""Ein Gesprächsschritt: Nachricht an die Session schicken, Antwort einsammeln."""

from dataclasses import dataclass, field

import anthropic


@dataclass
class TurnResult:
    text: str = ""
    stop: str = "end_turn"  # end_turn | budget_reached | refusal | retries_exhausted | error
    errors: list[str] = field(default_factory=list)


def create_session(client: anthropic.Anthropic, ids: dict, budget_cents: str, title: str) -> str:
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": ids["agent_id"], "version": ids["agent_version"]},
        environment_id=ids["environment_id"],
        title=title,
        budget={"type": "limit", "max_list_cost": {"amount": budget_cents, "currency": "USD"}},
    )
    return session.id


def collect(client: anthropic.Anthropic, session_id: str, events) -> TurnResult:
    """Wertet einen Event-Strom aus, bis die Session wieder auf Snow wartet."""
    result = TurnResult()
    parts: list[str] = []
    for event in events:
        if event.type == "agent.message":
            parts.extend(block.text for block in event.content if block.type == "text")
        elif event.type in ("agent.tool_use", "agent.mcp_tool_use") and (
            getattr(event, "evaluated_permission", None) == "ask"
        ):
            # Sollte bei always_allow nicht vorkommen. Niemand sitzt daneben: ablehnen.
            client.beta.sessions.events.send(
                session_id=session_id,
                events=[{
                    "type": "user.tool_confirmation",
                    "tool_use_id": event.id,
                    "result": "deny",
                    "deny_message": "Unbeaufsichtigter Telegram-Bot: keine Freigabe möglich.",
                }],
            )
        elif event.type == "session.error":
            result.errors.append(getattr(event.error, "message", str(event.error)))
        elif event.type == "session.status_idle":
            if event.stop_reason.type == "requires_action":
                continue  # wartet auf unsere Bestätigung – weiter zuhören
            result.stop = event.stop_reason.type
            break
        elif event.type == "session.status_terminated":
            result.stop = "error"
            break
    result.text = "\n\n".join(p.strip() for p in parts if p.strip())
    return result


def run_turn(client: anthropic.Anthropic, session_id: str, text: str) -> TurnResult:
    # Stream zuerst öffnen, dann senden – sonst kommen frühe Events gebündelt nach.
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )
        return collect(client, session_id, stream)
