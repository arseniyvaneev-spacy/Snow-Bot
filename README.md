# Snow-Bot

Snow AI und Agent Teacher als Bots für Telegram und für meine App.

Telegram-Bot für **Snow AI** (Recherche) und **Agent Teacher** (Lernen), betrieben auf Claude Managed Agents. Nur für einen einzigen Telegram-Nutzer.

## Wie es funktioniert

- Die Agenten liegen als versionierte Konfiguration bei Anthropic. `snow-bot-setup` legt sie einmal an und aktualisiert sie später.
- Pro Telegram-Chat und Agent gibt es eine Session. Anthropic speichert den Verlauf, der Bot nur die Session-IDs in `state/`.
- Beide Agenten haben **nur** `web_search` und `web_fetch`. Shell, Dateien und GitHub sind aus. Eine präparierte Webseite kann also nichts ausführen und nichts lesen.
  - Snow AI: freies Web (Umgebung mit offenem Netz, Sandbox leer und ohne Werkzeuge).
  - Agent Teacher: nur offizielle Claude- und Anthropic-Doku.
- Jede Unterhaltung hat eine harte Kostenobergrenze (`SESSION_BUDGET_CENTS`, Standard $2). Ist sie erreicht, startet `/neu` eine neue.
- Nur die User-ID in `TELEGRAM_ALLOWED_USER_ID` bekommt Antworten. Alle anderen werden ignoriert.
- **Snow Free** (`/free`, optional): kostenloser Chat über Cerebras, bei Ausfall über GitHub Models. Keine Websuche, der Verlauf (letzte 20 Nachrichten) liegt lokal in `state/free_history.json`.
- **Ohne Claude-Setup lauffähig:** Sind Gratis-Keys eingetragen, startet der Bot auch dann, wenn `snow-bot-setup` (noch) nicht geklappt hat oder `ANTHROPIC_API_KEY` fehlt – dann antwortet Snow Free, bis die Claude-Agenten eingerichtet sind.
- **Automatischer Ersatz:** Ist Claude nicht nutzbar (kein Guthaben, Ausgabenlimit, Rate-Limit, Störung, ungültiger Key), antwortet bei Snow AI und Agent Teacher automatisch Snow Free – mit Hinweis unter der Antwort.

## Einrichtung

1. Bot anlegen: In Telegram mit **@BotFather** sprechen, `/newbot`, Token notieren.
2. Eigene User-ID herausfinden, z. B. mit **@userinfobot**.
3. API-Key auf https://platform.claude.com anlegen.
4. Installieren – **Windows (PowerShell)**:

```powershell
git clone https://github.com/arseniyvaneev-spacy/Snow-Bot.git
cd Snow-Bot
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
notepad .env
```

   Meldet PowerShell beim Aktivieren „Ausführen von Skripts ist deaktiviert“, einmalig `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` ausführen.

   **macOS/Linux:**

```bash
git clone https://github.com/arseniyvaneev-spacy/Snow-Bot.git
cd Snow-Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # dann .env ausfüllen
```

5. In `.env` die drei Pflichtwerte eintragen: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `ANTHROPIC_API_KEY`. Die Programme lesen die Datei selbst – sie muss nur im Ordner liegen, aus dem du sie startest (dem Projektordner). Ein im Terminal gesetzter Wert hat Vorrang vor der Datei.
6. Agenten anlegen (einmalig, und erneut nach jeder Prompt-Änderung):

```bash
snow-bot-setup
```

## Start

Im Projektordner, mit aktivierter `.venv`:

```bash
snow-bot        # oder: python -m snow_bot
```

Beenden mit `Strg+C`. Ist Telegram beim Start oder später kurz nicht erreichbar, versucht der Bot es von selbst weiter – Warnungen wie `Timed out` im Fenster sind dann kein Grund zum Neustart. Der Bot nutzt Long Polling, braucht also keine öffentliche Adresse. Er muss aber laufen, solange du ihn nutzen willst (eigener Rechner, Raspberry Pi oder kleiner Server).

## Befehle

| Befehl | Wirkung |
|---|---|
| `/snow` | Snow AI aktiv schalten |
| `/teacher` | Agent Teacher aktiv schalten |
| `/free` | Snow Free aktiv schalten (gratis, ohne Websuche) |
| `/neu` | Neue Unterhaltung mit dem aktiven Agenten |
| `/status` | Zeigt den aktiven Agenten und die Gratis-Modelle |

## Umgebungsvariablen

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ja | Token von @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | ja | Deine Telegram-User-ID |
| `ANTHROPIC_API_KEY` | ja | Anthropic-API-Key |
| `SESSION_BUDGET_CENTS` | nein | Kostenobergrenze pro Unterhaltung in US-Cent (Standard 200) |
| `SNOW_BOT_STATE_DIR` | nein | Ordner für IDs und Sessions (Standard `./state`) |
| `CEREBRAS_API_KEY` | nein | Key für Snow Free (erste Wahl) |
| `CEREBRAS_MODEL` | nein | Standard `gpt-oss-120b` |
| `GITHUB_MODELS_TOKEN` | nein | GitHub-Token mit „Models: read“ (Ersatz für Cerebras) |
| `GITHUB_MODELS_MODEL` | nein | Standard `openai/gpt-4.1-mini` |

Keys gehören **nur** in die lokale `.env` (steht in `.gitignore`), nie in den Code – das Repo ist öffentlich.

## Prompts ändern

Die Prompts liegen in `src/snow_bot/prompts/`. Nach einer Änderung `snow-bot-setup` erneut ausführen, dann bekommt der Agent eine neue Version. Neue Unterhaltungen (`/neu`) nutzen sie, laufende behalten ihre alte Version.

## Kosten

Managed Agents berechnet Tokens zum Modellpreis, Websuchen ($10 pro 1.000) und Laufzeit ($0,08 pro Stunde aktiver Session). Die Session-Obergrenze begrenzt das pro Unterhaltung.
