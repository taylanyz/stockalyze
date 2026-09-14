"""
Sektör istatistikleri — F/K, PD/DD, ROE, marj için sektör medyanları.

Amaç: mutlak eşik yerine "bu hisse kendi sektörüne göre ucuz mu" sorusuna
cevap. Teknoloji F/K 30, banka F/K 5 normaldir — sektör medyanı bunu düzeltir.

Hesaplama pahalı (evren geneli yfinance .info) → günde bir, KVStore'da saklanır.
Yoksa/eskiyse skorlama mutlak eşiklere düşer (bozulmaz).
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_KEY = "sector_stats"
_MIN_PER_SECTOR = 3   # bundan az örnekli sektör medyanı güvenilmez


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def _quick_metrics(symbol: str) -> dict | None:
    """Tek sembol için hızlı temel oranlar + sektör (yfinance .info)."""
    import yfinance as yf

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        return None
    sector = info.get("sector")
    if not sector:
        return None
    return {
        "sector": sector,
        "pe": _f(info.get("trailingPE")),
        "pb": _f(info.get("priceToBook")),
        "roe": _f(info.get("returnOnEquity")),
        "margin": _f(info.get("profitMargins")),
    }


def _clip(values: list[float], lo: float, hi: float) -> list[float]:
    return [v for v in values if lo <= v <= hi]


def build_sector_stats(symbols: list[str]) -> dict:
    """
    Evren geneli sektör medyanları. Dönüş JSON-serileştirilebilir:
      {"sectors": {sektör: {count, pe_median, pb_median, roe_median, margin_median}},
       "computed_at": iso}
    """
    buckets: dict[str, dict[str, list[float]]] = {}
    for sym in symbols:
        m = _quick_metrics(sym)
        if m is None:
            continue
        b = buckets.setdefault(m["sector"], {"pe": [], "pb": [], "roe": [], "margin": []})
        for k in ("pe", "pb", "roe", "margin"):
            if m[k] is not None:
                b[k].append(m[k])

    sectors: dict[str, dict] = {}
    for sec, b in buckets.items():
        # aşırı uçları temizle (yfinance BIST verisinde bozuk PD/DD olabiliyor)
        pe = _clip(b["pe"], 0.5, 200)
        pb = _clip(b["pb"], 0.05, 50)
        roe = _clip(b["roe"], -2, 5)
        mg = _clip(b["margin"], -1, 1)
        n = max(len(pe), len(pb))
        if n < _MIN_PER_SECTOR:
            continue
        sectors[sec] = {
            "count": n,
            "pe_median": round(statistics.median(pe), 2) if pe else None,
            "pb_median": round(statistics.median(pb), 2) if pb else None,
            "roe_median": round(statistics.median(roe), 4) if roe else None,
            "margin_median": round(statistics.median(mg), 4) if mg else None,
        }

    return {"sectors": sectors, "computed_at": datetime.now(timezone.utc).isoformat()}
