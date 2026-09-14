"""
analysis/technical.py için birim testler.

Dikkat: hiç ağa çıkmıyoruz. Elle kurgulanmış bir DataFrame veriyoruz.
Bu, teknik göstergeleri saf fonksiyon olarak yazmanın getirisi.

Çalıştırma:  python -m pytest -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.technical import compute_technical, rsi_wilder


def _make_df(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def test_rsi_sabit_yukselen_seride_100_e_yaklasir():
    # Her gün artan seri -> hiç kayıp yok -> RSI = 100.
    closes = pd.Series(np.arange(1, 60, dtype=float))
    rsi = rsi_wilder(closes).iloc[-1]
    assert rsi == 100.0


def test_rsi_bilinen_deger_araligi():
    closes = pd.Series([44, 44.3, 44.1, 43.6, 44.3, 44.8, 45.1, 45.4,
                        45.4, 45.0, 44.9, 44.3, 44.1, 43.6, 44.3, 44.8])
    rsi = rsi_wilder(closes, period=14).iloc[-1]
    assert 0 <= rsi <= 100


def test_yukselen_trend_tespiti():
    # 260 gün boyunca istikrarlı yükseliş: fiyat > SMA50 > SMA200 beklenir.
    closes = list(np.linspace(100, 200, 260))
    tech = compute_technical("TEST", _make_df(closes))
    assert tech.trend.value == "Yükseliş"
    assert tech.sma_50 > tech.sma_200


def test_eksik_veri_none_birakir_cökmez():
    # Sadece 10 gün: SMA50/200 hesaplanamaz ama fonksiyon patlamamalı.
    tech = compute_technical("TEST", _make_df([100.0] * 10))
    assert tech.sma_50 is None
    assert tech.sma_200 is None
    assert tech.data_points == 10
    assert tech.trend_age_days is None


def test_trend_yasi_ve_oncesi():
    # 220 gün düşüş, sonra 180 gün yükseliş -> bugün yükseliş trendi,
    # yaşı makul, öncesinde düşüş/yatay.
    closes = list(np.linspace(200, 100, 220)) + list(np.linspace(100, 180, 180))
    tech = compute_technical("TEST", _make_df(closes))
    assert tech.trend.value == "Yükseliş"
    assert tech.trend_age_days and tech.trend_age_days > 30
    assert tech.prior_trend is not None and tech.prior_trend.value != "Yükseliş"


def test_trend_yasi_tum_gecmis_boyunca_oncesi_yok():
    closes = list(np.linspace(100, 300, 400))   # kesintisiz yükseliş
    tech = compute_technical("TEST", _make_df(closes))
    assert tech.trend.value == "Yükseliş"
    assert tech.prior_trend is None   # seri veri başından beri sürüyor
