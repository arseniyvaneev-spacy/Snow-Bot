"""Liest die Konfiguration zentral aus Umgebungsvariablen."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_env_file(path: Path | None = None) -> bool:
    """Lädt `.env` aus dem aktuellen Ordner, falls vorhanden.

    Bereits gesetzte Umgebungsvariablen gewinnen (override=False), damit man einzelne
    Werte im Terminal überschreiben kann. `interpolate=False`, damit ein `$` in einem
    Token nicht als Variable ausgewertet wird. Gibt zurück, ob eine Datei gelesen wurde.
    """
    datei = path or Path.cwd() / ".env"
    if not datei.is_file():
        return False
    return load_dotenv(datei, override=False, interpolate=False)


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
        raise ConfigError(f"{name} fehlt – in .env eintragen (Vorlage: .env.example).")
    return wert


def state_dir() -> Path:
    """Ordner für IDs und Sitzungen. Enthält keine Secrets, gehört aber nicht ins Git."""
    return Path(os.environ.get("SNOW_BOT_STATE_DIR", "state")).expanduser()


def load() -> Config:
    load_env_file()
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
