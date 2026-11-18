# Agenten als Claude-Projekte

Snow AI und Agent Teacher ohne API: als **Projekte** in der Claude-App (iPhone, Desktop, claude.ai). Läuft über das normale Claude-Konto, braucht kein API-Guthaben.

## Einrichten (pro Agent einmal)

1. Claude-App oder claude.ai öffnen → **Projekte** → **Neues Projekt**.
2. Name: `Snow AI` bzw. `Agent Teacher`.
3. **Projektanweisungen** (Instructions) öffnen und den gesamten Inhalt von [`snow-ai.md`](snow-ai.md) bzw. [`agent-teacher.md`](agent-teacher.md) hineinkopieren.
4. Optional für Agent Teacher: Dateien aus deinen Repos (z. B. Agenten-Dateien) als Projektwissen hochladen, damit sie daran anknüpfen kann.
5. Für Recherche die **Websuche** in der Unterhaltung einschalten, falls dein Tarif sie hat.

## Unterschied zum Telegram-Bot

| | Claude-Projekt | Snow-Bot (Telegram) |
|---|---|---|
| Kosten | im Claude-Abo | API-Guthaben |
| „Nur lesend“ | Verhaltensregel im Prompt | technisch erzwungen (nur Web-Werkzeuge) |
| Teacher nur offizielle Doku | Verhaltensregel | technisch erzwungen (Domain-Liste) |
| Formatierung | Markdown | reiner Text |

Die Prompts sind aus `src/snow_bot/prompts/` abgeleitet. Bei Änderungen dort diese Fassungen mitziehen.
