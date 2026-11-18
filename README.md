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

## Einrichtung

1. Bot anlegen: In Telegram mit **@BotFather** sprechen, `/newbot`, Token notieren.
2. Eigene User-ID herausfinden, z. B. mit **@userinfobot**.
3. API-Key auf https://platform.claude.com anlegen.
4. Installieren:

```bash
# mit uv
uv venv && uv pip install -e ".[dev]"

# ohne uv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

5. `.env.example` nach `.env` kopieren und ausfüllen, dann laden: `set -a; source .env; set +a`
6. Agenten anlegen (einmalig, und erneut nach jeder Prompt-Änderung):

```bash
snow-bot-setup
```

## Start

```bash
snow-bot        # oder: python -m snow_bot
```

Der Bot nutzt Long Polling, braucht also keine öffentliche Adresse. Er muss aber laufen, solange du ihn nutzen willst (eigener Rechner, Raspberry Pi oder kleiner Server).

## Befehle

| Befehl | Wirkung |
|---|---|
| `/snow` | Snow AI aktiv schalten |
| `/teacher` | Agent Teacher aktiv schalten |
| `/neu` | Neue Unterhaltung mit dem aktiven Agenten |
| `/status` | Zeigt den aktiven Agenten |

## Umgebungsvariablen

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ja | Token von @BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | ja | Deine Telegram-User-ID |
| `ANTHROPIC_API_KEY` | ja | Anthropic-API-Key |
| `SESSION_BUDGET_CENTS` | nein | Kostenobergrenze pro Unterhaltung in US-Cent (Standard 200) |
| `SNOW_BOT_STATE_DIR` | nein | Ordner für IDs und Sessions (Standard `./state`) |

## Prompts ändern

Die Prompts liegen in `src/snow_bot/prompts/`. Nach einer Änderung `snow-bot-setup` erneut ausführen, dann bekommt der Agent eine neue Version. Neue Unterhaltungen (`/neu`) nutzen sie, laufende behalten ihre alte Version.

## Kosten

Managed Agents berechnet Tokens zum Modellpreis, Websuchen ($10 pro 1.000) und Laufzeit ($0,08 pro Stunde aktiver Session). Die Session-Obergrenze begrenzt das pro Unterhaltung.
