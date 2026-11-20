"""Einstieg: python -m snow_bot  bzw.  snow-bot"""

import logging
import sys

from snow_bot.bot import POLL_TIMEOUT, SnowBot
from snow_bot.config import ConfigError, load
from snow_bot.netz import warte_auf_telegram


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # loggt sonst die Token-URL
    try:
        bot = SnowBot(load())
    except (ConfigError, RuntimeError) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return 1
    log = logging.getLogger("snow_bot")
    log.info("Verbinde mit Telegram …")
    warte_auf_telegram()  # z. B. direkt nach dem PC-Start, wenn das Netz noch fehlt
    # Wiederholungen von python-telegram-bot nur sichtbar machen, nicht verschweigen.
    logging.getLogger("telegram.ext._utils.networkloop").setLevel(logging.DEBUG)
    # bootstrap_retries=-1: Ist Telegram beim Start kurz nicht erreichbar, endlos neu
    # versuchen statt abstürzen. Netzfehler im laufenden Betrieb fängt run_polling selbst ab.
    bot.build().run_polling(timeout=POLL_TIMEOUT, bootstrap_retries=-1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
