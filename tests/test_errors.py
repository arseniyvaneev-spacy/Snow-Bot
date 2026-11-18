import anthropic
import httpx2 as httpx
import pytest

from snow_bot.errors import GUTHABEN, erklaere


def antwort(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/agents"))


def fehler(cls, status, message):
    return cls(message, response=antwort(status), body=None)


def test_kein_guthaben():
    msg = "Your credit balance is too low to access the Anthropic API."
    assert erklaere(fehler(anthropic.BadRequestError, 400, msg)) == GUTHABEN


def test_anderer_400_ist_nicht_guthaben():
    assert erklaere(fehler(anthropic.BadRequestError, 400, "invalid tools")) != GUTHABEN


@pytest.mark.parametrize(
    ("cls", "status", "stichwort"),
    [
        (anthropic.AuthenticationError, 401, "ungültig"),
        (anthropic.PermissionDeniedError, 403, "Managed Agents"),
        (anthropic.RateLimitError, 429, "Minute"),
        (anthropic.InternalServerError, 500, "Problem"),
    ],
)
def test_statuscodes(cls, status, stichwort):
    assert stichwort in erklaere(fehler(cls, status, "x"))
