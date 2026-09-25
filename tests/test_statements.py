"""analysis/statements.py — büyüme / trend çıkarımı (saf, ağ yok)."""

from __future__ import annotations

from src.analysis.statements import summarize, year_over_year
from src.models import FinancialHistory, FinancialPeriod


def _p(year, rev, ni, eq, debt, ocf=None, annual=True):
    return FinancialPeriod(
        label=f"{year}/12", year=year, period=12, is_annual=annual,
        revenue=rev, net_income=ni, operating_profit=ni, equity=eq,
        total_debt=debt, operating_cash_flow=ocf,
    )


def _hist(*periods):
    return FinancialHistory(symbol="X", currency="TRY", source="test", periods=list(periods))


def test_yoy_buyume():
    h = _hist(_p(2023, 100, 10, 50, 50), _p(2024, 130, 15, 60, 55))
    yoy = year_over_year(h)
    assert len(yoy) == 1
    assert abs(yoy[0].revenue_growth - 0.30) < 1e-9
    assert abs(yoy[0].net_income_growth - 0.50) < 1e-9


def test_summarize_marj_ve_borc_trendi():
    # marj %10 -> %20 (iyileşiyor), borç/özkaynak 1.0 -> 0.5 (iyileşiyor)
    h = _hist(
        _p(2022, 100, 10, 100, 100, ocf=9),
        _p(2023, 120, 15, 130, 90, ocf=13),
        _p(2024, 150, 30, 200, 100, ocf=28),
    )
    lines = " ".join(text for text, _tag in summarize(h))
    tags = [tag for _text, tag in summarize(h)]
    assert "Satış" in lines
    assert "iyileşmiş" in lines             # marj VEYA borç
    assert "kâr kalitesi iyi" in lines      # ocf net kârı karşılıyor
    assert "olumlu" in tags                 # en az bir olumlu etiket var


def test_negatiften_pozitife_buyume_none():
    h = _hist(_p(2023, 100, -5, 50, 50), _p(2024, 120, 10, 55, 50))
    assert year_over_year(h)[0].net_income_growth is None


def test_tek_yil_yetersiz():
    h = _hist(_p(2024, 100, 10, 50, 50))
    assert summarize(h) == [("Trend çıkarımı için yeterli yıllık veri yok.", "notr")]
