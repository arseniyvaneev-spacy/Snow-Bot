"""Einstieg: python -m snow_bot  bzw.  snow-bot"""

import logging
import sys

from snow_bot.bot import SnowBot
from snow_bot.config import ConfigError, load


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
    bot.build().run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
