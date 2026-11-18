"""Einmaliges Setup: legt Agenten und Umgebungen an bzw. aktualisiert sie.

Aufruf: snow-bot-setup  (oder python -m snow_bot.setup_agents)
Speichert die IDs in <state>/ids.json, und zwar nach jedem Schritt – bricht das Setup
mittendrin ab, bleiben keine verwaisten Agenten zurück. Erneut ausführen, nachdem du
einen Prompt geändert hast: Der Agent bekommt dann eine neue Version, statt neu
angelegt zu werden.
"""

import os
import sys

import anthropic

from snow_bot.agents import MODEL, SPECS
from snow_bot.config import load_env_file, state_dir
from snow_bot.state import JsonStore


def sync(client: anthropic.Anthropic, store: JsonStore) -> dict:
    ids = store.load()
    for key, spec in SPECS.items():
        entry = ids.setdefault(key, {})

        if "environment_id" not in entry:
            env = client.beta.environments.create(**spec.environment)
            entry["environment_id"] = env.id
            store.save(ids)
            print(f"[{key}] Umgebung angelegt: {env.id}")
        else:
            client.beta.environments.update(
                environment_id=entry["environment_id"], config=spec.environment["config"]
            )
            print(f"[{key}] Umgebung aktualisiert: {entry['environment_id']}")

        fields = {
            "name": spec.name,
            "model": {"id": MODEL, "effort": spec.effort},
            "system": spec.system_prompt(),
            "tools": spec.tools(),
        }
        if "agent_id" not in entry:
            agent = client.beta.agents.create(**fields)
            print(f"[{key}] Agent angelegt: {agent.id} (Version {agent.version})")
        else:
            agent = client.beta.agents.update(agent_id=entry["agent_id"], **fields)
            print(f"[{key}] Agent aktualisiert: {agent.id} (Version {agent.version})")
        entry["agent_id"] = agent.id
        entry["agent_version"] = agent.version
        store.save(ids)
    return ids


def main() -> int:
    load_env_file()
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("Fehler: ANTHROPIC_API_KEY fehlt (in .env eintragen).", file=sys.stderr)
        return 1
    store = JsonStore(state_dir() / "ids.json")
    try:
        sync(anthropic.Anthropic(), store)
    except anthropic.AuthenticationError:
        print("Fehler: ANTHROPIC_API_KEY fehlt oder ist ungültig.", file=sys.stderr)
        return 1
    print(f"Gespeichert in {store.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
