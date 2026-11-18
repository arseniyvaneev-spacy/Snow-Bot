"""Übersetzt API-Fehler in kurze, verständliche Meldungen auf Deutsch."""

import anthropic

GUTHABEN = (
    "Auf deinem Anthropic-API-Konto ist kein Guthaben. Lade es auf "
    "https://platform.claude.com unter Billing auf (ein Claude-Abo gilt nicht für die API)."
)


def erklaere(fehler: anthropic.APIError) -> str:
    """Kurze Erklärung ohne Traceback. Enthält nie den API-Key."""
    text = str(getattr(fehler, "message", "") or fehler)
    if isinstance(fehler, anthropic.BadRequestError) and "credit balance" in text.lower():
        return GUTHABEN
    if isinstance(fehler, anthropic.AuthenticationError):
        return "Der ANTHROPIC_API_KEY ist ungültig oder abgelaufen. Prüf ihn in der .env."
    if isinstance(fehler, anthropic.PermissionDeniedError):
        return "Der API-Key hat keinen Zugriff auf diese Funktion (Managed Agents)."
    if isinstance(fehler, anthropic.RateLimitError):
        return "Zu viele Anfragen gerade. Versuch es in einer Minute nochmal."
    if isinstance(fehler, anthropic.APIConnectionError):
        return "Keine Verbindung zur Claude-API. Internet prüfen und nochmal versuchen."
    if isinstance(fehler, anthropic.InternalServerError):
        return "Die Claude-API hat gerade ein Problem. Versuch es gleich nochmal."
    anfrage = getattr(fehler, "request_id", None)
    zusatz = f" (Request-ID {anfrage})" if anfrage else ""
    return f"Fehler bei der Claude-API: {type(fehler).__name__}{zusatz}."
