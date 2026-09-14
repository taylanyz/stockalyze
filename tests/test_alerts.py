"""alerts.py — kural tetikleme mantığı (saf, ağ yok)."""

from __future__ import annotations

from src.analysis.alerts import check_alerts
from src.models import (
    Market,
    RSIZone,
    StockEvaluation,
    StockSnapshot,
    TechnicalIndicators,
    Trend,
)
from src.storage.alerts_repo import AlertRule


def _ev(price=100.0, rsi=50.0, cross=None):
    snap = StockSnapshot(symbol="X.IS", name="X", market=Market.BIST, currency="TRY",
                         price=price, previous_close=price, day_change_pct=0,
                         market_cap=1e9, sector="Industrials", exchange="IST")
    tech = TechnicalIndicators(
        symbol="X.IS", as_of="2026-01-01", data_points=300, last_close=price,
        sma_50=price, sma_200=price, price_vs_sma50_pct=0, price_vs_sma200_pct=0,
        trend=Trend.UP, cross_signal=cross, rsi_14=rsi, rsi_zone=RSIZone.NEUTRAL,
        volume_last=1, volume_avg_20=1, volume_ratio=1.0,
    )
    return StockEvaluation(symbol="X.IS", snapshot=snap, technical=tech)


def _rule(kind, thr, last_fired=None):
    return AlertRule(id=1, symbol="X.IS", kind=kind, threshold=thr, active=1,
                     last_fired=last_fired)


def test_price_above_tetikler():
    t = check_alerts([_rule("price_above", 90)], {"X.IS": _ev(price=100)})
    assert len(t) == 1 and "fiyat" in t[0].message


def test_price_above_tetiklemez():
    assert check_alerts([_rule("price_above", 110)], {"X.IS": _ev(price=100)}) == []


def test_rsi_below():
    t = check_alerts([_rule("rsi_below", 30)], {"X.IS": _ev(rsi=25)})
    assert len(t) == 1


def test_golden_cross_taze():
    t = check_alerts([_rule("golden_cross", None)],
                     {"X.IS": _ev(cross="Altın kesişim (2 gün önce)")})
    assert len(t) == 1
    assert check_alerts([_rule("golden_cross", None)],
                        {"X.IS": _ev(cross="Altın kesişim (20 gün önce)")}) == []


def test_bugun_tetiklenmisse_atlanir():
    from datetime import date
    r = _rule("price_above", 90, last_fired=date.today().isoformat())
    assert check_alerts([r], {"X.IS": _ev(price=100)}) == []


def test_pasif_kural_atlanir():
    r = AlertRule(id=1, symbol="X.IS", kind="price_above", threshold=90,
                  active=0, last_fired=None)
    assert check_alerts([r], {"X.IS": _ev(price=100)}) == []
