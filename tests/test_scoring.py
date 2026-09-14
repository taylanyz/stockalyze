"""
analysis/scoring.py için birim testler.

Puanlama saf ve deterministik: aynı metrik sözlüğü -> aynı puan.
Ağ yok.
"""

from __future__ import annotations

from src.analysis.scoring import score_metrics
from src.models import Market


def test_guclu_hisse_yuksek_puan():
    m = {
        "pe_trailing": 12, "price_to_book": 2, "profit_margin": 0.30,
        "return_on_equity": 0.25, "debt_to_equity": 0.4, "current_ratio": 2.0,
        "trend": "Yükseliş", "price_vs_sma200_pct": 15, "rsi_14": 55,
        "volume_ratio": 1.8,
    }
    score = score_metrics(m, Market.US)
    assert score.total >= 85
    assert score.verdict == "Yakından bakmaya değer"


def test_zayif_hisse_dusuk_puan():
    m = {
        "pe_trailing": 60, "price_to_book": 10, "profit_margin": -0.05,
        "return_on_equity": -0.10, "debt_to_equity": 3.0, "current_ratio": 0.6,
        "trend": "Düşüş", "price_vs_sma200_pct": -20, "rsi_14": 75,
        "volume_ratio": 0.3,
    }
    score = score_metrics(m, Market.US)
    assert score.total <= 20


def test_bist_ve_us_esikleri_farkli():
    # F/K 8: BIST'te "orta" (0), ABD'de "ucuz" (+15).
    m = {"pe_trailing": 8, "trend": "Yatay / Karışık"}
    us = score_metrics(m, Market.US)
    bist = score_metrics(m, Market.BIST)
    assert us.total > bist.total


def test_bos_metrik_notr_taban():
    score = score_metrics({}, Market.US)
    assert score.total == 50
    assert score.reasons == []


def test_puan_0_100_arasinda_kirpilir():
    m = {"pe_trailing": 1, "price_to_book": 0.1, "profit_margin": 0.9,
         "return_on_equity": 0.9, "debt_to_equity": 0.0, "current_ratio": 9,
         "trend": "Yükseliş", "price_vs_sma200_pct": 50, "rsi_14": 50,
         "volume_ratio": 3}
    assert score_metrics(m, Market.US).total == 100
