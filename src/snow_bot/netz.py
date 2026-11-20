"""Prüft vor dem Start, ob Telegram erreichbar ist, und sagt sichtbar, worauf er wartet."""

import logging
import socket
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

TELEGRAM_HOST = "api.telegram.org"


def telegram_erreichbar(host: str = TELEGRAM_HOST, timeout: float = 10.0) -> str | None:
    """None, wenn eine TCP-Verbindung zu Port 443 klappt, sonst ein kurzer Grund."""
    try:
        adressen = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return (
            f"{host} lässt sich nicht auflösen (DNS). Internet, VPN oder DNS-Einstellung prüfen."
        )
    for familie, typ, proto, _, adresse in adressen:
        try:
            with socket.socket(familie, typ, proto) as s:
                s.settimeout(timeout)
                s.connect(adresse)
            return None
        except OSError:
            continue
    return f"{host} ist aufgelöst, aber nicht erreichbar (Firewall, VPN oder Virenscanner?)."


def warte_auf_telegram(
    pruefen: Callable[[], str | None] = telegram_erreichbar,
    pause: float = 15.0,
    schlafen: Callable[[float], None] = time.sleep,
) -> None:
    """Blockiert, bis Telegram erreichbar ist, und meldet jeden Fehlversuch im Fenster."""
    versuch = 0
    while (grund := pruefen()) is not None:
        versuch += 1
        log.warning(
            "Warte auf Verbindung zu Telegram (Versuch %d): %s Neuer Versuch in %d s.",
            versuch, grund, pause,
        )
        schlafen(pause)
    if versuch:
        log.info("Telegram ist wieder erreichbar.")
