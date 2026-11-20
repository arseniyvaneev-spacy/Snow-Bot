from snow_bot.netz import telegram_erreichbar, warte_auf_telegram


def test_wartet_bis_erreichbar_und_meldet(caplog):
    antworten = iter(["DNS kaputt.", "DNS kaputt.", None])
    pausen: list[float] = []
    with caplog.at_level("WARNING"):
        warte_auf_telegram(lambda: next(antworten), pause=3, schlafen=pausen.append)
    assert pausen == [3, 3]
    assert caplog.text.count("Warte auf Verbindung zu Telegram") == 2
    assert "DNS kaputt." in caplog.text


def test_sofort_erreichbar_wartet_nicht():
    pausen: list[float] = []
    warte_auf_telegram(lambda: None, schlafen=pausen.append)
    assert pausen == []


def test_unbekannter_host_ist_dns_fehler():
    grund = telegram_erreichbar("gibt-es-nicht.invalid", timeout=1)
    assert grund is not None and "DNS" in grund
