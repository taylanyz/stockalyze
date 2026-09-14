"""screener.py + portfolio.py saf mantık testleri (ağ yok)."""

from __future__ import annotations

from src.analysis.portfolio import build_portfolio
from src.analysis.screener import ScreenFilters, run_screener
from src.models import (
    Fundamentals,
    Market,
    RSIZone,
    StockEvaluation,
    StockSnapshot,
    TechnicalIndicators,
    Trend,
)
from src.storage.portfolio_repo import Position


def _ev(sym, market, price, pe, roe, trend, rsi, div=None, name=None):
    snap = StockSnapshot(symbol=sym, name=name or sym, market=market, currency="TRY",
                         price=price, previous_close=price, day_change_pct=0,
                         market_cap=1e9, sector="Industrials", exchange="IST")
    fund = Fundamentals(symbol=sym, pe_trailing=pe, pe_forward=None, price_to_book=1.0,
                        profit_margin=0.1, operating_margin=0.1, return_on_equity=roe,
                        debt_to_equity=0.5, current_ratio=1.5, dividend_yield=div)
    tech = TechnicalIndicators(
        symbol=sym, as_of="2026-01-01", data_points=300, last_close=price,
        sma_50=price, sma_200=price, price_vs_sma50_pct=1, price_vs_sma200_pct=5,
        trend=trend, cross_signal=None, rsi_14=rsi, rsi_zone=RSIZone.NEUTRAL,
        volume_last=1, volume_avg_20=1, volume_ratio=1.0,
    )
    return StockEvaluation(symbol=sym, snapshot=snap, fundamentals=fund, technical=tech)


def test_screener_fk_ve_trend_filtresi():
    evals = [
        _ev("A.IS", Market.BIST, 10, pe=6, roe=0.25, trend=Trend.UP, rsi=55),
        _ev("B.IS", Market.BIST, 10, pe=40, roe=0.05, trend=Trend.UP, rsi=55),
        _ev("C.IS", Market.BIST, 10, pe=6, roe=0.25, trend=Trend.DOWN, rsi=55),
    ]
    f = ScreenFilters(max_pe=10, min_roe=0.15, trends={"Yükseliş"}, min_score=None)
    hits = run_screener(evals, f)
    assert [h.ev.symbol for h in hits] == ["A.IS"]


def test_screener_puana_gore_sirali():
    evals = [
        _ev("LOW.IS", Market.BIST, 10, pe=30, roe=0.05, trend=Trend.SIDEWAYS, rsi=50),
        _ev("HIGH.IS", Market.BIST, 10, pe=5, roe=0.30, trend=Trend.UP, rsi=55),
    ]
    hits = run_screener(evals, ScreenFilters(min_score=None))
    assert hits[0].ev.symbol == "HIGH.IS"
    assert hits[0].score >= hits[1].score


def test_portfolio_deger_ve_kz():
    ev = _ev("X.IS", Market.BIST, price=120, pe=10, roe=0.2, trend=Trend.UP, rsi=50,
             div=0.04, name="X A.S.")
    pos = [Position("X.IS", quantity=10, buy_price=100, buy_date="2026-01-01", note=None)]
    s = build_portfolio(pos, {"X.IS": ev})
    h = s.holdings[0]
    assert h.cost == 1000
    assert h.value == 1200
    assert h.pnl == 200
    assert abs(h.pnl_pct - 0.20) < 1e-9
    assert abs(s.est_annual_dividend - 48) < 1e-9   # 1200 * 0.04
    assert abs(s.total_pnl_pct - 0.20) < 1e-9


def test_portfolio_eksik_sembol():
    pos = [Position("YOK.IS", 5, 10, None, None)]
    s = build_portfolio(pos, {})
    assert s.missing == ["YOK.IS"]
    assert s.holdings == []
