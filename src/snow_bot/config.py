"""Liest die Konfiguration zentral aus Umgebungsvariablen."""

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Eine Pflichtvariable fehlt oder ist ungültig."""


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_user_id: int
    state_dir: Path
    session_budget_cents: str


def _pflicht(name: str) -> str:
    wert = os.environ.get(name, "").strip()
    if not wert:
        raise ConfigError(f"Umgebungsvariable {name} fehlt (siehe .env.example).")
    return wert


def state_dir() -> Path:
    """Ordner für IDs und Sitzungen. Enthält keine Secrets, gehört aber nicht ins Git."""
    return Path(os.environ.get("SNOW_BOT_STATE_DIR", "state")).expanduser()


def load() -> Config:
    user_id = _pflicht("TELEGRAM_ALLOWED_USER_ID")
    if not user_id.isdigit():
        raise ConfigError("TELEGRAM_ALLOWED_USER_ID muss eine Zahl sein (deine Telegram-User-ID).")
    budget = os.environ.get("SESSION_BUDGET_CENTS", "200").strip()
    if not budget.isdigit() or budget.startswith("0"):
        raise ConfigError(
            "SESSION_BUDGET_CENTS muss eine positive ganze Zahl sein, z. B. 200 = $2."
        )
    # ANTHROPIC_API_KEY liest das Anthropic-SDK selbst.
    _pflicht("ANTHROPIC_API_KEY")
    return Config(
        telegram_token=_pflicht("TELEGRAM_BOT_TOKEN"),
        allowed_user_id=int(user_id),
        state_dir=state_dir(),
        session_budget_cents=budget,
    )
