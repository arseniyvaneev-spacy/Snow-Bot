"""Telegram-Oberfläche: Befehle, Zugriffsschutz, Weiterleitung an die Agenten."""

import asyncio
import logging
from collections import defaultdict

import anthropic
from telegram import LinkPreviewOptions, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from snow_bot.agents import SPECS
from snow_bot.config import Config
from snow_bot.runner import TurnResult, create_session, run_turn
from snow_bot.state import JsonStore, SessionStore

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096
NAMES = {"snow": "Snow AI", "teacher": "Agent Teacher"}

HILFE = (
    "Befehle:\n"
    "/snow – mit Snow AI sprechen (Recherche)\n"
    "/teacher – mit Agent Teacher sprechen (Lernen)\n"
    "/neu – neue Unterhaltung mit dem aktiven Agenten\n"
    "/status – welcher Agent gerade aktiv ist"
)


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Teilt lange Antworten, bevorzugt an Absätzen, dann an Zeilen, notfalls hart."""
    teile: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        schnitt = rest.rfind("\n\n", 0, limit)
        if schnitt <= 0:
            schnitt = rest.rfind("\n", 0, limit)
        if schnitt <= 0:
            schnitt = limit
        teile.append(rest[:schnitt].rstrip())
        rest = rest[schnitt:].lstrip()
    if rest:
        teile.append(rest)
    return teile


def describe(result: TurnResult, budget_cents: str) -> str:
    text = result.text
    if result.stop == "budget_reached":
        dollar = int(budget_cents) / 100
        text += f"\n\n(Budget dieser Unterhaltung erreicht: ${dollar:.2f}. /neu startet eine neue.)"
    elif result.stop == "refusal":
        text += "\n\n(Die Anfrage wurde von einem Sicherheitsfilter abgelehnt.)"
    elif result.stop in ("retries_exhausted", "error"):
        text += "\n\n(Es gab ein Problem beim Ausführen. Versuch es nochmal oder /neu.)"
    if result.errors:
        log.warning("Session-Fehler: %s", result.errors)
    return text.strip() or "(Keine Antwort erhalten.)"


class SnowBot:
    def __init__(self, config: Config, client: anthropic.Anthropic | None = None) -> None:
        self.config = config
        self.client = client or anthropic.Anthropic()
        self.ids = JsonStore(config.state_dir / "ids.json").load()
        missing = [k for k in SPECS if "agent_id" not in self.ids.get(k, {})]
        if missing:
            fehlend = ", ".join(missing)
            raise RuntimeError(f"Agenten fehlen ({fehlend}). Erst snow-bot-setup ausführen.")
        self.sessions = SessionStore(JsonStore(config.state_dir / "sessions.json"))
        self.locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def build(self) -> Application:
        app = Application.builder().token(self.config.telegram_token).build()
        nur_ich = filters.User(user_id=self.config.allowed_user_id)
        app.add_handler(CommandHandler(["start", "hilfe"], self.cmd_start, filters=nur_ich))
        app.add_handler(CommandHandler("snow", self.cmd_switch, filters=nur_ich))
        app.add_handler(CommandHandler("teacher", self.cmd_switch, filters=nur_ich))
        app.add_handler(CommandHandler("neu", self.cmd_new, filters=nur_ich))
        app.add_handler(CommandHandler("status", self.cmd_status, filters=nur_ich))
        app.add_handler(MessageHandler(nur_ich & filters.TEXT & ~filters.COMMAND, self.on_text))
        # Alle anderen Nutzer bekommen keine Antwort – der Bot verrät nicht einmal, dass er lebt.
        return app

    async def cmd_start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        aktiv = NAMES[self.sessions.active_agent(update.effective_chat.id)]
        await update.message.reply_text(f"Hallo Snow. Aktiv: {aktiv}.\n\n{HILFE}")

    async def cmd_switch(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        key = update.message.text.lstrip("/").split("@")[0].split()[0]
        self.sessions.set_active(update.effective_chat.id, key)
        await update.message.reply_text(f"{NAMES[key]} ist jetzt aktiv.")

    async def cmd_new(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        key = self.sessions.active_agent(chat)
        self.sessions.forget_session(chat, key)
        await update.message.reply_text(
            f"Neue Unterhaltung mit {NAMES[key]} beginnt mit deiner nächsten Nachricht."
        )

    async def cmd_status(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        key = self.sessions.active_agent(chat)
        laeuft = "läuft" if self.sessions.session_id(chat, key) else "noch keine"
        await update.message.reply_text(f"Aktiv: {NAMES[key]} (Unterhaltung: {laeuft}).")

    def _turn(self, chat: int, key: str, text: str) -> TurnResult:
        session_id = self.sessions.session_id(chat, key)
        if session_id is None:
            session_id = create_session(
                self.client,
                self.ids[key],
                self.config.session_budget_cents,
                f"Telegram {NAMES[key]}",
            )
            self.sessions.set_session(chat, key, session_id)
        return run_turn(self.client, session_id, text)

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        async with self.locks[chat]:  # eine Anfrage pro Chat zur Zeit
            key = self.sessions.active_agent(chat)
            await context.bot.send_chat_action(chat, ChatAction.TYPING)
            try:
                result = await asyncio.to_thread(self._turn, chat, key, update.message.text)
            except anthropic.NotFoundError:
                self.sessions.forget_session(chat, key)
                await update.message.reply_text(
                    "Die alte Unterhaltung gibt es nicht mehr. Schick die Nachricht bitte nochmal."
                )
                return
            except anthropic.APIError as fehler:
                log.exception("API-Fehler")
                await update.message.reply_text(
                    f"Fehler bei der Claude-API: {type(fehler).__name__}. Versuch es gleich nochmal"
                )
                return
            for teil in split_message(describe(result, self.config.session_budget_cents)):
                await update.message.reply_text(
                    teil, link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
