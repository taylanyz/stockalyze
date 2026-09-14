"""radar.py saf mantık testleri — konumlanma notu + ilgi puanı (ağ yok)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.radar import _attention, positioning_note
from src.analysis.technical import compute_technical
from src.models import RSIZone, Trend


def _tech(trend: Trend, zone: RSIZone, cross: str | None = None):
    # compute_technical yerine elle bir TechnicalIndicators kurmak yerine
    # gerçek fonksiyonu besleyip trendi/zone'u ayarlamak zor; küçük bir sahte.
    from src.models import TechnicalIndicators
    return TechnicalIndicators(
        symbol="X", as_of="2026-01-01", data_points=300,
        last_close=100, sma_50=95, sma_200=90,
        price_vs_sma50_pct=5, price_vs_sma200_pct=11,
        trend=trend, cross_signal=cross,
        rsi_14=75 if zone is RSIZone.OVERBOUGHT else 25 if zone is RSIZone.OVERSOLD else 50,
        rsi_zone=zone, volume_last=1, volume_avg_20=1, volume_ratio=1.0,
    )


def test_dusus_trendi_alici_icin_riskli():
    note, tag = positioning_note(_tech(Trend.DOWN, RSIZone.NEUTRAL), holding=False)
    assert tag == "riskli"
    assert "düş" in note.lower()


def test_yukselis_asiri_alim_temkinli():
    note, tag = positioning_note(_tech(Trend.UP, RSIZone.OVERBOUGHT), holding=True)
    assert tag == "temkinli"
    assert "geri çekilme" in note


def test_yukselis_saglikli_olumlu():
    _, tag = positioning_note(_tech(Trend.UP, RSIZone.NEUTRAL), holding=False)
    assert tag == "olumlu"


def test_taze_kesisim_notu_one_ekler():
    note, _ = positioning_note(
        _tech(Trend.UP, RSIZone.NEUTRAL, cross="Altın kesişim (2 gün önce)"), holding=False)
    assert note.startswith("Yeni altın kesişim;")


def test_attention_yuksek_hacim_ve_hareket():
    a = _attention(volume_ratio=3.0, day_change_pct=8.0, ret_5d_pct=15.0)
    assert a >= 90
    assert _attention(None, None, None) == 0


def test_sideways_notr():
    _, tag = positioning_note(_tech(Trend.SIDEWAYS, RSIZone.NEUTRAL), holding=False)
    assert tag == "notr"
