"""Telegram-Oberfläche: Befehle, Zugriffsschutz, Weiterleitung an die Agenten."""

import asyncio
import logging
import os
from collections import defaultdict

import anthropic
from telegram import LinkPreviewOptions, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from snow_bot.agents import SPECS
from snow_bot.config import Config
from snow_bot.errors import erklaere, fallback_sinnvoll
from snow_bot.free_llm import FreeAnswer, FreeChat, FreeLLMError
from snow_bot.runner import TurnResult, create_session, run_turn
from snow_bot.state import JsonStore, SessionStore

log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096
POLL_TIMEOUT = 25  # Sekunden, die Telegram eine Long-Polling-Anfrage offen hält
NAMES = {"snow": "Snow AI", "teacher": "Agent Teacher", "free": "Snow Free"}

HILFE = (
    "Befehle:\n"
    "/snow – mit Snow AI sprechen (Recherche)\n"
    "/teacher – mit Agent Teacher sprechen (Lernen)\n"
    "/free – kostenloser Chat ohne Websuche (Cerebras/GitHub)\n"
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


def describe_free(antwort: FreeAnswer, fallback_grund: str | None = None) -> str:
    text = antwort.text
    quelle = f"{antwort.provider}, {antwort.model}"
    if fallback_grund:
        text += (
            f"\n\n(Claude nicht erreichbar: {fallback_grund} "
            f"Antwort von {quelle}, ohne Websuche.)"
        )
    elif antwort.provider != "Cerebras":
        text += f"\n\n(Antwort von {quelle}.)"
    return text


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
    def __init__(
        self,
        config: Config,
        client: anthropic.Anthropic | None = None,
        free: FreeChat | None = None,
    ) -> None:
        self.config = config
        self.free = free or FreeChat(
            list(config.free_providers), JsonStore(config.state_dir / "free_history.json")
        )
        self.ids = JsonStore(config.state_dir / "ids.json").load()
        # Claude-Agenten, die snow-bot-setup fertig angelegt hat.
        self.ready = {k for k in SPECS if "agent_id" in self.ids.get(k, {})}
        if client is None and not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            self.ready = set()  # ohne Key kein Claude
        fehlend = [k for k in SPECS if k not in self.ready]
        if fehlend and not self.free.available:
            raise RuntimeError(
                f"Agenten fehlen ({', '.join(fehlend)}). Erst snow-bot-setup ausführen "
                "oder CEREBRAS_API_KEY / GITHUB_MODELS_TOKEN für den Gratis-Modus eintragen."
            )
        if fehlend:
            log.warning(
                "Claude-Agenten fehlen (%s) – bis snow-bot-setup klappt, antwortet Snow Free.",
                ", ".join(fehlend),
            )
        self.client = client or (anthropic.Anthropic() if self.ready else None)
        self.sessions = SessionStore(JsonStore(config.state_dir / "sessions.json"))
        self.locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def build(self) -> Application:
        # Großzügige Wartezeiten: Bei langsamem Netz lieber warten als abbrechen.
        app = (
            Application.builder()
            .token(self.config.telegram_token)
            .connect_timeout(20)
            .read_timeout(30)
            .write_timeout(30)
            .pool_timeout(10)
            .get_updates_connect_timeout(20)
            .get_updates_read_timeout(40)  # muss länger sein als POLL_TIMEOUT
            .build()
        )
        nur_ich = filters.User(user_id=self.config.allowed_user_id)
        app.add_handler(CommandHandler(["start", "hilfe"], self.cmd_start, filters=nur_ich))
        app.add_handler(CommandHandler("snow", self.cmd_switch, filters=nur_ich))
        app.add_handler(CommandHandler("teacher", self.cmd_switch, filters=nur_ich))
        app.add_handler(CommandHandler("free", self.cmd_switch, filters=nur_ich))
        app.add_handler(CommandHandler("neu", self.cmd_new, filters=nur_ich))
        app.add_handler(CommandHandler("status", self.cmd_status, filters=nur_ich))
        app.add_handler(MessageHandler(nur_ich & filters.TEXT & ~filters.COMMAND, self.on_text))
        # Alle anderen Nutzer bekommen keine Antwort – der Bot verrät nicht einmal, dass er lebt.
        return app

    def active(self, chat: int) -> str:
        """Gewählter Agent – oder Snow Free, wenn der gewählte nicht eingerichtet ist."""
        key = self.sessions.active_agent(chat)
        if key in SPECS and key not in self.ready and self.free.available:
            return "free"
        return key

    async def cmd_start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        aktiv = NAMES[self.active(update.effective_chat.id)]
        await update.message.reply_text(f"Hallo Snow. Aktiv: {aktiv}.\n\n{HILFE}")

    async def cmd_switch(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        key = update.message.text.lstrip("/").split("@")[0].split()[0]
        if key == "free" and not self.free.available:
            await update.message.reply_text(
                "Snow Free ist nicht eingerichtet: CEREBRAS_API_KEY oder GITHUB_MODELS_TOKEN "
                "in .env eintragen und den Bot neu starten."
            )
            return
        if key in SPECS and key not in self.ready:
            await update.message.reply_text(
                f"{NAMES[key]} ist noch nicht eingerichtet: snow-bot-setup ausführen "
                "(braucht Guthaben auf dem Anthropic-API-Konto). Bis dahin antwortet Snow Free."
            )
            return
        self.sessions.set_active(update.effective_chat.id, key)
        await update.message.reply_text(f"{NAMES[key]} ist jetzt aktiv.")

    async def cmd_new(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        key = self.active(chat)
        if key == "free":
            self.free.reset(chat)
        else:
            self.sessions.forget_session(chat, key)
        await update.message.reply_text(
            f"Neue Unterhaltung mit {NAMES[key]} beginnt mit deiner nächsten Nachricht."
        )

    async def cmd_status(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        key = self.active(chat)
        if key == "free":
            laeuft = "läuft" if self.free.history(chat) else "noch keine"
        else:
            laeuft = "läuft" if self.sessions.session_id(chat, key) else "noch keine"
        gratis = self.free.describe()
        claude = ", ".join(NAMES[k] for k in SPECS if k in self.ready) or "keine (Setup fehlt)"
        await update.message.reply_text(
            f"Aktiv: {NAMES[key]} (Unterhaltung: {laeuft}).\n"
            f"Claude-Agenten: {claude}\nGratis-Modelle: {gratis}"
        )

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

    async def _reply(self, update: Update, text: str) -> None:
        for teil in split_message(text):
            await update.message.reply_text(
                teil, link_preview_options=LinkPreviewOptions(is_disabled=True)
            )

    async def _free_turn(self, update: Update, fallback_grund: str | None = None) -> None:
        chat = update.effective_chat.id
        try:
            antwort = await asyncio.to_thread(self.free.chat, chat, update.message.text)
        except FreeLLMError as fehler:
            text = str(fehler)
            if fallback_grund:
                text = f"{fallback_grund}\n\nAuch der Gratis-Ersatz klappte nicht: {text}"
            await update.message.reply_text(text)
            return
        await self._reply(update, describe_free(antwort, fallback_grund))

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat.id
        async with self.locks[chat]:  # eine Anfrage pro Chat zur Zeit
            key = self.active(chat)
            await context.bot.send_chat_action(chat, ChatAction.TYPING)
            if key == "free":
                await self._free_turn(update)
                return
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
                if self.free.available and fallback_sinnvoll(fehler):
                    await self._free_turn(update, fallback_grund=erklaere(fehler))
                else:
                    await update.message.reply_text(erklaere(fehler))
                return
            await self._reply(update, describe(result, self.config.session_budget_cents))
