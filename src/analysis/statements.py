"""
Bilanço Karnesi analizi — mali tablo geçmişinden büyüme / trend çıkarımı.

Saf fonksiyonlar: girdi FinancialHistory, çıktı sayı / kısa metin.
Tahmin değil, tarif: "satış büyüyor mu, marj bozuluyor mu, borç artıyor mu".
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models import FinancialHistory, FinancialPeriod


@dataclass
class YoY:
    label: str
    revenue_growth: float | None       # kesir (0.15 = %15)
    net_income_growth: float | None


def _annuals(history: FinancialHistory) -> list[FinancialPeriod]:
    return [p for p in history.periods if p.is_annual]


def _growth(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    # negatiften pozitife geçişte yüzde anlamsız olur
    if old < 0 < new:
        return None
    return (new - old) / abs(old)


def year_over_year(history: FinancialHistory) -> list[YoY]:
    """Ardışık tam yıllar arası büyüme (eski -> yeni)."""
    annuals = _annuals(history)
    out: list[YoY] = []
    for prev, cur in zip(annuals, annuals[1:]):
        out.append(YoY(
            label=cur.label,
            revenue_growth=_growth(cur.revenue, prev.revenue),
            net_income_growth=_growth(cur.net_income, prev.net_income),
        ))
    return out


def _trend_word(first: float | None, last: float | None, *, higher_is_better: bool) -> str:
    if first is None or last is None:
        return ""
    diff = last - first
    tol = 0.02   # 2 puanlık band = "stabil"
    if abs(diff) < tol:
        return "stabil"
    improving = (diff > 0) == higher_is_better
    return "iyileşiyor" if improving else "bozuluyor"


def summarize(history: FinancialHistory) -> list[str]:
    """Bilanço Karnesi'nden kısa, madde madde çıkarımlar."""
    annuals = _annuals(history)
    if len(annuals) < 2:
        return ["Trend çıkarımı için yeterli yıllık veri yok."]

    first, last = annuals[0], annuals[-1]
    lines: list[str] = []

    # Satış büyümesi (son yıl + çok yıllık CAGR)
    yoy = year_over_year(history)
    if yoy and yoy[-1].revenue_growth is not None:
        g = yoy[-1].revenue_growth
        lines.append(f"Satış son yıl %{g * 100:+.0f}.")
    if (first.revenue and last.revenue and last.revenue > 0 and first.revenue > 0
            and len(annuals) >= 3):
        n = len(annuals) - 1
        cagr = (last.revenue / first.revenue) ** (1 / n) - 1
        lines.append(f"Satış {n} yıllık ortalama büyüme %{cagr * 100:+.0f} (yıllık).")

    # Net kâr büyümesi
    if yoy and yoy[-1].net_income_growth is not None:
        lines.append(f"Net kâr son yıl %{yoy[-1].net_income_growth * 100:+.0f}.")

    # Marj trendi
    w = _trend_word(first.net_margin, last.net_margin, higher_is_better=True)
    if w and first.net_margin is not None and last.net_margin is not None:
        lines.append(
            f"Net marj %{first.net_margin * 100:.0f} → %{last.net_margin * 100:.0f} ({w})."
        )

    # Borç/özkaynak trendi
    w = _trend_word(first.debt_to_equity, last.debt_to_equity, higher_is_better=False)
    if w and first.debt_to_equity is not None and last.debt_to_equity is not None:
        lines.append(
            f"Borç/özkaynak {first.debt_to_equity:.1f} → {last.debt_to_equity:.1f} ({w})."
        )

    # Nakit akışı kalitesi — nakit akışı net kârı karşılıyor mu?
    if last.operating_cash_flow is not None and last.net_income and last.net_income > 0:
        ratio = last.operating_cash_flow / last.net_income
        if ratio >= 0.8:
            lines.append("Faaliyet nakit akışı net kârı karşılıyor (kâr kalitesi iyi).")
        elif ratio < 0.4:
            lines.append("Faaliyet nakit akışı net kârın altında (kâr kalitesine dikkat).")

    return lines or ["Belirgin bir trend çıkarılamadı."]
