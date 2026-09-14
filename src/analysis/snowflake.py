"""
Özet Profil ("kar tanesi") — hisseyi 5 eksende 0-100 puanlar.

  Değer · Kârlılık · Sağlık · Büyüme · Temettü

Puanla AYNI verilere dayanır ama sayı yerine PROFİL gösterir:
büyük dengeli şekil = her yönden güçlü; sivri şekil = bazı yönlerden zayıf.
Yatırım tavsiyesi değildir.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.analysis.statements import year_over_year
from src.models import FinancialHistory, Fundamentals, StockEvaluation

AXES = ["Değer", "Kârlılık", "Sağlık", "Büyüme", "Temettü"]


@dataclass
class Snowflake:
    values: dict[str, float | None]   # eksen -> 0-100 (veri yoksa None)

    @property
    def total(self) -> float | None:
        vals = [v for v in self.values.values() if v is not None]
        return sum(vals) / len(vals) if vals else None


def _band(value: float | None, bands: list[tuple[float, float]], *, invert=False) -> float | None:
    """bands: [(üst_sınır, puan), ...] artan sınır sırasında."""
    if value is None:
        return None
    v = -value if invert else value
    for upper, score in bands:
        if v <= upper:
            return score
    return bands[-1][1]


def _avg(*scores: float | None) -> float | None:
    xs = [s for s in scores if s is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _value_axis(f: Fundamentals | None) -> float | None:
    if f is None:
        return None
    pe = _band(f.pe_trailing, [(8, 90), (15, 72), (25, 52), (40, 32), (1e9, 15)])
    pb = _band(f.price_to_book, [(1, 90), (2, 72), (4, 50), (8, 30), (1e9, 15)])
    return _avg(pe, pb)


def _profitability_axis(f: Fundamentals | None) -> float | None:
    if f is None:
        return None
    roe = _band(f.return_on_equity, [(0, 10), (0.05, 30), (0.10, 48), (0.15, 65),
                                     (0.25, 82), (1e9, 92)])
    nm = _band(f.profit_margin, [(0, 12), (0.05, 35), (0.10, 52), (0.20, 72), (1e9, 88)])
    om = _band(f.operating_margin, [(0, 12), (0.05, 35), (0.10, 52), (0.20, 72), (1e9, 88)])
    return _avg(roe, nm, om)


def _health_axis(f: Fundamentals | None) -> float | None:
    if f is None:
        return None
    de = _band(f.debt_to_equity, [(0.3, 92), (0.6, 78), (1.0, 62), (2.0, 42), (1e9, 20)])
    cr = _band(f.current_ratio, [(0.8, 25), (1.0, 45), (1.5, 68), (2.5, 85), (1e9, 78)])
    return _avg(de, cr)


def _growth_axis(history: FinancialHistory | None) -> float | None:
    if history is None:
        return None
    yoy = year_over_year(history)
    if not yoy:
        return None
    g = yoy[-1].revenue_growth
    n = yoy[-1].net_income_growth
    rev = _band(g, [(-0.05, 10), (0.05, 32), (0.15, 52), (0.30, 72), (1e9, 90)])
    ni = _band(n, [(-0.10, 15), (0.0, 38), (0.15, 55), (0.35, 75), (1e9, 90)])
    return _avg(rev, ni)


def _dividend_axis(f: Fundamentals | None) -> float | None:
    if f is None or f.dividend_yield is None:
        return 10.0 if f is not None else None   # temettü yok = düşük ama bilinen
    return _band(f.dividend_yield, [(0.0, 12), (0.01, 32), (0.03, 52), (0.05, 72),
                                    (0.08, 88), (1e9, 80)])


def compute_snowflake(
    ev: StockEvaluation, history: FinancialHistory | None = None
) -> Snowflake:
    f = ev.fundamentals
    return Snowflake(values={
        "Değer": _value_axis(f),
        "Kârlılık": _profitability_axis(f),
        "Sağlık": _health_axis(f),
        "Büyüme": _growth_axis(history),
        "Temettü": _dividend_axis(f),
    })
