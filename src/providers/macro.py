"""
Makro / piyasa nabzı verisi.

Çoğu yfinance'ten (döviz, endeks, emtia, VIX). TCMB EVDS (politika faizi,
enflasyon) için ücretsiz API key gerekir — yoksa o kısım atlanır.

Key kaynakları (sırayla): st.secrets["TCMB_EVDS_KEY"], env TCMB_EVDS_KEY,
data/evds_key.txt.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# (görünen ad, yfinance sembolü, birim, yükseliş iyi mi)
_MARKET = [
    ("USD/TRY", "USDTRY=X", "₺", False),
    ("EUR/TRY", "EURTRY=X", "₺", False),
    ("BIST 100", "XU100.IS", "", True),
    ("S&P 500", "^GSPC", "", True),
    ("VIX (oynaklık)", "^VIX", "", False),
    ("Altın (ons)", "GC=F", "$", None),
    ("Brent petrol", "BZ=F", "$", None),
    ("Dolar endeksi (DXY)", "DX-Y.NYB", "", None),
]


@dataclass
class MacroMetric:
    name: str
    symbol: str
    unit: str
    value: float | None
    change_pct: float | None          # günlük %
    week_change_pct: float | None      # ~5 gün
    history: pd.Series | None          # son ~3 ay kapanış (sparkline)
    higher_is_good: bool | None


def _load_evds_key() -> str | None:
    try:
        import streamlit as st

        k = st.secrets.get("TCMB_EVDS_KEY")
        if k:
            return str(k)
    except Exception:
        pass
    if os.environ.get("TCMB_EVDS_KEY"):
        return os.environ["TCMB_EVDS_KEY"]
    p = Path(__file__).resolve().parents[2] / "data" / "evds_key.txt"
    if p.exists():
        v = p.read_text(encoding="utf-8").strip()
        return v or None
    return None


class MacroProvider:
    def market_metrics(self) -> list[MacroMetric]:
        import yfinance as yf

        out: list[MacroMetric] = []
        for name, sym, unit, hig in _MARKET:
            try:
                h = yf.Ticker(sym).history(period="3mo")["Close"].dropna()
            except Exception as e:
                log.info("macro %s hata: %s", sym, e)
                h = pd.Series(dtype=float)
            if len(h) < 2:
                out.append(MacroMetric(name, sym, unit, None, None, None, None, hig))
                continue
            last = float(h.iloc[-1])
            day = (last - h.iloc[-2]) / h.iloc[-2] * 100 if h.iloc[-2] else None
            wk = (last - h.iloc[-6]) / h.iloc[-6] * 100 if len(h) >= 6 and h.iloc[-6] else None
            out.append(MacroMetric(name, sym, unit, last, day, wk, h, hig))
        return out

    # ---- TCMB EVDS (opsiyonel) ---------------------------------------

    def tcmb_metrics(self) -> list[MacroMetric]:
        """
        EVDS'ten politika faizi + yıllık enflasyon + TCMB USD alış.
        `evds` paketi kullanılır (TCMB API'si 2024'te değişti; paket bunu yönetir).
        Key yoksa veya paket yoksa boş liste döner.
        """
        key = _load_evds_key()
        if not key:
            return []
        try:
            from evds import evdsAPI
        except ImportError:
            log.info("`evds` paketi yok — TCMB verisi atlandı.")
            return []

        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=900)
        api = evdsAPI(key)

        # (ad, seri kodu, birim, formül)  formül 3 = yıllık % değişim
        want = [
            ("Politika faizi (1H repo) %", "TP.APIFON4", "%", ""),
            ("Yıllık enflasyon (TÜFE) %", "TP.FG.J0", "%", "3"),
            ("TCMB USD (alış) ₺", "TP.DK.USD.A.YTL", "₺", ""),
        ]
        out: list[MacroMetric] = []
        for name, code, unit, formula in want:
            try:
                df = api.get_data(
                    [code], startdate=f"{start:%d-%m-%Y}", enddate=f"{end:%d-%m-%Y}",
                    formulas=formula,
                )
                col = next(c for c in df.columns if c != "Tarih")
                s = pd.to_numeric(df[col], errors="coerce").dropna()
                if s.empty:
                    continue
                out.append(MacroMetric(
                    name, code, unit, float(s.iloc[-1]), None, None,
                    s.tail(24).reset_index(drop=True), higher_is_good=False,
                ))
            except Exception as e:  # noqa: BLE001
                log.info("EVDS %s hata: %s", code, e)
        return out
