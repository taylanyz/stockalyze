"""
Piyasa tarayıcı — "bugün ne hareketleniyor" verisi.

İki kaynak:
  - ABD: yfinance'in hazır tarayıcıları (day_gainers / day_losers / most_actives)
  - BIST: hazır tarayıcı yok -> bir sembol listesini (BIST 30) toplu indirip
    günlük değişime göre kendimiz sıralıyoruz.

Bu modül yfinance'e sıkı bağlı (tarayıcı yfinance'e özgü bir özellik),
o yüzden ayrı tutuldu; Evaluator/analysis buna doğrudan bağımlı değil.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from src.models import Market
from src.providers.yfinance_provider import detect_market

log = logging.getLogger(__name__)


@dataclass
class Mover:
    symbol: str
    name: str
    market: Market
    price: float | None
    day_change_pct: float | None
    volume: float | None
    currency: str | None = None
    score: int | None = None      # trending.py isteğe bağlı doldurur


_US_SCREENS = {
    "gainers": "day_gainers",
    "losers": "day_losers",
    "actives": "most_actives",
}


class MarketScreener:
    def us_movers(self, kind: str, count: int = 15) -> list[Mover]:
        """kind: 'gainers' | 'losers' | 'actives'."""
        screen_id = _US_SCREENS[kind]
        try:
            res = yf.screen(screen_id, count=count)
        except Exception as e:
            log.warning("yfinance screen(%s) hata: %s", screen_id, e)
            return []
        quotes = res.get("quotes", []) if isinstance(res, dict) else (res or [])
        out: list[Mover] = []
        for q in quotes:
            sym = q.get("symbol")
            if not sym:
                continue
            out.append(Mover(
                symbol=sym,
                name=q.get("shortName") or q.get("longName") or sym,
                market=Market.US,
                price=_f(q.get("regularMarketPrice")),
                day_change_pct=_f(q.get("regularMarketChangePercent")),
                volume=_f(q.get("regularMarketVolume")),
                currency=q.get("currency") or "USD",
            ))
        return out

    def bist_movers(self, symbols: list[str], top: int = 10) -> dict[str, list[Mover]]:
        """
        BIST evrenini toplu indir, günlük değişime göre sırala.
        Dönüş: {'gainers': [...], 'losers': [...], 'actives': [...]}
        """
        movers = self._bulk(symbols)
        with_change = [m for m in movers if m.day_change_pct is not None]
        gainers = sorted(
            [m for m in with_change if m.day_change_pct > 0],
            key=lambda m: m.day_change_pct, reverse=True,
        )
        losers = sorted(
            [m for m in with_change if m.day_change_pct < 0],
            key=lambda m: m.day_change_pct,
        )
        by_volume = sorted(
            [m for m in movers if m.volume is not None],
            key=lambda m: m.volume, reverse=True,
        )
        return {
            "gainers": gainers[:top],
            "losers": losers[:top],
            "actives": by_volume[:top],
        }

    def bulk_history(
        self, symbols: list[str], period: str = "1y"
    ) -> dict[str, pd.DataFrame]:
        """
        Çok sayıda sembolün OHLCV geçmişini TEK indirmede getir.

        Radar için kritik: 60 sembolün trend/RSI/hacmini tek tek çekmek
        yerine bir bulk indirmeyle alıp yerelde hesaplıyoruz.
        Dönüş: {sembol: DataFrame(Open/High/Low/Close/Volume)}
        """
        if not symbols:
            return {}
        try:
            raw = yf.download(
                symbols, period=period, progress=False, group_by="ticker",
                threads=True, auto_adjust=True,
            )
        except Exception as e:
            log.warning("bulk_history indirme hatası: %s", e)
            return {}

        cols = ["Open", "High", "Low", "Close", "Volume"]
        out: dict[str, pd.DataFrame] = {}
        for s in symbols:
            try:
                d = (raw[s] if len(symbols) > 1 else raw)[cols].dropna()
            except (KeyError, TypeError):
                continue
            if len(d) >= 2:
                out[s] = d
        return out

    # ---- iç ----------------------------------------------------------

    def _bulk(self, symbols: list[str]) -> list[Mover]:
        out: list[Mover] = []
        for s, d in self.bulk_history(symbols, period="5d").items():
            last = _f(d["Close"].iloc[-1])
            prev = _f(d["Close"].iloc[-2])
            change = (last - prev) / prev * 100 if (last is not None and prev) else None
            mk = detect_market(s)
            out.append(Mover(
                symbol=s,
                name=s.removesuffix(".IS"),
                market=mk,
                price=last,
                day_change_pct=change,
                volume=_f(d["Volume"].iloc[-1]),
                currency="TRY" if mk is Market.BIST else "USD",
            ))
        return out


def _f(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if isinstance(v, pd.Series):
        return None
    return None if f != f else f
