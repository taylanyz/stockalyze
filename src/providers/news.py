"""
Haber sağlayıcı.

İki kaynak:
  - market_news(): Türkçe finans RSS akışları (genel piyasa/ekonomi haberleri)
  - ticker_news(symbol): yfinance'in hisse-bazlı haberi (ABD'de iyi, BIST'te zayıf)

Sadece BAŞLIK + KAYNAK + LİNK + ZAMAN toplarız — haberi okumaz, özetlemez,
yorumlamayız. Puanlamayı etkilemez; tamamen bilgilendirme amaçlıdır.

RSS akışları belgesizdir ve format değiştirebilir — her biri ayrı try/except
içinde; biri çökerse diğerleri görünmeye devam eder.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)

# Genel piyasa haberi RSS akışları.
# (ad, url, keyword_filtresi_gerekli_mi)
#   - Investing akışları zaten temiz -> filtre yok
#   - Dünya / Bloomberg HT genel gazete -> yalnızca finans başlıklarını al
_RSS_FEEDS = [
    ("Investing TR", "https://tr.investing.com/rss/market_overview.rss", False),
    ("Investing TR – Döviz/Makro", "https://tr.investing.com/rss/news_1.rss", False),
    ("Dünya", "https://www.dunya.com/rss", True),
    ("Bloomberg HT", "https://www.bloomberght.com/rss", True),
]
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_TIMEOUT = 12

# Filtreli akışlarda: başlıkta bu terimlerden biri geçmiyorsa ele (spor/magazin).
_FINANCE_TERMS = (
    "borsa", "bist", "hisse", "endeks", "faiz", "dolar", "euro", "sterlin", "yen ",
    "altın", "gümüş", "enflasyon", "tcmb", "merkez bankas", "fed", "ecb", "bilanço",
    "temettü", "halka arz", "şirket", "ihracat", "ithalat", "kredi", "tahvil", "bono",
    "fon ", "yatırım", "piyasa", "ekonomi", "büyüme", "cari açık", "bütçe", "vergi",
    "petrol", "emtia", "kripto", "bitcoin", "sermaye", " kur", "rezerv", "swap",
    "kâr ", "zarar", "ciro", "gelir", "spk", "kap ", "bankas", "holding", "sanayi",
)


def _passes_finance_filter(title: str) -> bool:
    low = title.lower()
    return any(t in low for t in _FINANCE_TERMS)


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published: datetime | None       # UTC; bilinmiyorsa None
    image_url: str | None = None     # yalnızca yfinance hisse haberinde dolu

    @property
    def age_text(self) -> str:
        if self.published is None:
            return ""
        delta = datetime.now(timezone.utc) - self.published
        secs = delta.total_seconds()
        if secs < 0:
            return "az önce"
        if secs < 3600:
            return f"{int(secs // 60)} dk önce"
        if secs < 86400:
            return f"{int(secs // 3600)} saat önce"
        return f"{int(secs // 86400)} gün önce"


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    # 1) RFC 822 ("Tue, 08 Sep 2026 11:47:00 +0300")
    try:
        d = parsedate_to_datetime(raw)
        return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    # 2) ISO ("2026-09-08T09:03:31Z" / "2026-09-08 09:03:31")
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(raw, fmt)
            return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_rss(raw: bytes, source: str) -> list[NewsItem]:
    """Ham RSS/XML -> NewsItem listesi. (Saf fonksiyon; test edilebilir.)"""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.info("RSS parse hatası (%s): %s", source, e)
        return []
    out: list[NewsItem] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        out.append(NewsItem(
            title=title, source=source, url=link,
            published=_parse_date(item.findtext("pubDate")),
        ))
    return out


class NewsProvider:
    def market_news(self, limit: int = 15) -> list[NewsItem]:
        """Tüm RSS akışlarını çek, birleştir, tekrarları at, yeniden eskiye sırala."""
        # Tek bir akış listeyi ele geçirmesin diye kaynak başına sınır.
        per_source_cap = max(4, (limit // len(_RSS_FEEDS)) + 3)

        items: list[NewsItem] = []
        for source, url, needs_filter in _RSS_FEEDS:
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                    feed = parse_rss(r.read(), source)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                log.info("RSS alınamadı (%s): %s", source, e)
                continue

            if needs_filter:
                feed = [n for n in feed if _passes_finance_filter(n.title)]
            feed.sort(
                key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            items.extend(feed[:per_source_cap])

        seen: set[str] = set()
        unique: list[NewsItem] = []
        for it in items:
            key = it.title.lower()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(it)

        unique.sort(
            key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return unique[:limit]

    def ticker_news(self, symbol: str, limit: int = 8) -> list[NewsItem]:
        """yfinance'ten hisse-bazlı haber. ABD'de dolu, BIST'te çoğunlukla boş."""
        try:
            import yfinance as yf

            raw = yf.Ticker(symbol).news or []
        except Exception as e:
            log.info("ticker_news(%s) hata: %s", symbol, e)
            return []

        out: list[NewsItem] = []
        for entry in raw:
            c = entry.get("content", entry)  # yeni yfinance: content alt-nesnesi
            title = (c.get("title") or entry.get("title") or "").strip()
            if not title:
                continue

            prov = c.get("provider")
            source = (prov.get("displayName") if isinstance(prov, dict)
                      else entry.get("publisher")) or "—"

            url = (
                (c.get("clickThroughUrl") or {}).get("url")
                or (c.get("canonicalUrl") or {}).get("url")
                or entry.get("link")
                or ""
            )

            pub = c.get("pubDate")
            published = _parse_date(pub)
            if published is None and entry.get("providerPublishTime"):
                try:
                    published = datetime.fromtimestamp(
                        entry["providerPublishTime"], tz=timezone.utc
                    )
                except (TypeError, ValueError, OSError):
                    published = None

            thumb = c.get("thumbnail") or entry.get("thumbnail") or {}
            image = thumb.get("originalUrl")
            if not image:
                res = thumb.get("resolutions") or []
                image = res[0].get("url") if res else None

            out.append(NewsItem(
                title=title, source=source, url=url,
                published=published, image_url=image,
            ))
        return out[:limit]
