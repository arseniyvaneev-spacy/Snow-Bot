"""Definition der beiden Agenten und ihrer Umgebungen.

Beide Agenten haben ausschließlich web_search und web_fetch. Alle Sandbox-Werkzeuge
(bash, read, write, edit, glob, grep) sind aus: Eine präparierte Webseite kann so
nichts ausführen, nichts lesen und nichts schreiben.
"""

from dataclasses import dataclass
from importlib.resources import files

MODEL = "claude-opus-5-5"

# Offizielle Doku, die Agent Teacher lesen darf (und sonst nichts).
TEACHER_DOMAINS = [
    "code.claude.com",
    "docs.claude.com",
    "platform.claude.com",
    "claude.com",
    "anthropic.com",
    "modelcontextprotocol.io",
]


@dataclass(frozen=True)
class AgentSpec:
    key: str  # interner Name, z. B. "snow"
    name: str  # Anzeigename in der Console
    prompt_file: str
    effort: str
    allowed_domains: list[str] | None  # None = keine Einschränkung
    environment: dict

    def system_prompt(self) -> str:
        return files("snow_bot.prompts").joinpath(self.prompt_file).read_text(encoding="utf-8")

    def tools(self) -> list[dict]:
        web = []
        for tool in ("web_search", "web_fetch"):
            entry: dict = {
                "name": tool,
                "enabled": True,
                # Nur lesende Web-Werkzeuge in einer leeren Sandbox: ohne Rückfrage ausführen.
                "permission_policy": {"type": "always_allow"},
            }
            if self.allowed_domains:
                entry["allowed_domains"] = self.allowed_domains
            web.append(entry)
        return [
            {
                "type": "agent_toolset_20260401",
                "default_config": {"enabled": False},
                "configs": web,
            }
        ]


SPECS: dict[str, AgentSpec] = {
    "snow": AgentSpec(
        key="snow",
        name="Snow AI (Telegram)",
        prompt_file="snow-ai.md",
        effort="high",
        allowed_domains=None,
        # Freie Recherche braucht offenes Netz. Die Sandbox ist dabei leer und ohne Werkzeuge.
        environment={
            "name": "snow-ai-web",
            "config": {"type": "cloud", "networking": {"type": "unrestricted"}},
        },
    ),
    "teacher": AgentSpec(
        key="teacher",
        name="Agent Teacher (Telegram)",
        prompt_file="agent-teacher.md",
        effort="medium",
        allowed_domains=TEACHER_DOMAINS,
        # Unter "limited" gelten allowed_hosts auch für web_search / web_fetch.
        environment={
            "name": "agent-teacher-docs",
            "config": {
                "type": "cloud",
                "networking": {
                    "type": "limited",
                    "allowed_hosts": [h for d in TEACHER_DOMAINS for h in (d, f"*.{d}")],
                },
            },
        },
    ),
}
