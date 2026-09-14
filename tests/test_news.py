"""news.py saf mantık testleri — RSS parse + tarih + yaş metni (ağ yok)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.providers.news import (
    NewsItem,
    _parse_date,
    _passes_finance_filter,
    parse_rss,
)

_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Piyasalar gune yukselisle basladi</title>
    <link>https://example.com/haber1</link>
    <pubDate>Tue, 08 Sep 2026 11:47:00 +0300</pubDate>
  </item>
  <item>
    <title>Baslik var ama link yok</title>
    <pubDate>Tue, 08 Sep 2026 10:00:00 +0300</pubDate>
  </item>
  <item>
    <title>Ikinci gecerli haber</title>
    <link>https://example.com/haber2</link>
  </item>
</channel></rss>"""


def test_parse_rss_gecerli_itemlari_alir():
    items = parse_rss(_RSS, "Test")
    assert [i.title for i in items] == [
        "Piyasalar gune yukselisle basladi", "Ikinci gecerli haber",
    ]
    assert items[0].source == "Test"
    assert items[0].url == "https://example.com/haber1"
    assert items[0].published is not None
    assert items[1].published is None


def test_parse_rss_bozuk_xml_bos_liste():
    assert parse_rss(b"<not-xml", "Test") == []


def test_parse_date_formatlari():
    assert _parse_date("Tue, 08 Sep 2026 11:47:00 +0300").tzinfo is not None
    assert _parse_date("2026-09-08T09:03:31Z").hour == 9
    assert _parse_date("2026-09-08 09:03:31") is not None
    assert _parse_date(None) is None
    assert _parse_date("saçma sapan") is None


def test_finance_filtresi():
    assert _passes_finance_filter("TCMB faiz kararını açıkladı")
    assert _passes_finance_filter("Borsa İstanbul günü yükselişle kapattı")
    assert _passes_finance_filter("X Holding bilanço açıkladı")
    assert not _passes_finance_filter("Galatasaray - Sporting maçı bu akşam")
    assert not _passes_finance_filter("İstanbul Coffee Festival başlıyor")


def test_age_text():
    now = datetime.now(timezone.utc)
    assert NewsItem("t", "s", "u", now - timedelta(minutes=5)).age_text == "5 dk önce"
    assert NewsItem("t", "s", "u", now - timedelta(hours=3)).age_text == "3 saat önce"
    assert NewsItem("t", "s", "u", now - timedelta(days=2)).age_text == "2 gün önce"
    assert NewsItem("t", "s", "u", None).age_text == ""
