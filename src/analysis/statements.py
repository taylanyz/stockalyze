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


def _growth_note(g: float) -> tuple[str, str]:
    """(etiket, açıklama) — bir büyüme oranı (kesir) için. Aynı eşikler her
    yerde (satış, kâr) tutarlı kullanılsın diye tek yerde toplanır."""
    if g > 0.15:
        return "olumlu", "güçlü bir büyüme"
    if g > 0.05:
        return "olumlu", "ılımlı bir büyüme"
    if g >= -0.05:
        return "notr", "durağan bir seyir"
    return "riskli", "belirgin bir daralma"


def _margin_note(diff: float) -> tuple[str, str]:
    """(etiket, açıklama) — net marj değişimi için (diff = son - ilk, kesir)."""
    if diff >= 0.05:
        return "olumlu", "belirgin şekilde iyileşmiş; şirket her satıştan daha fazla kâr bırakıyor"
    if diff >= 0.02:
        return "olumlu", "hafif iyileşmiş"
    if diff > -0.02:
        return "notr", "stabil kalmış"
    if diff > -0.05:
        return "temkinli", "hafif bozulmuş"
    return "riskli", "belirgin şekilde bozulmuş; kârlılık zayıflıyor"


def _debt_note(diff: float) -> tuple[str, str]:
    """(etiket, açıklama) — borç/özkaynak değişimi için (diff = son - ilk)."""
    if diff <= -0.3:
        return "olumlu", "belirgin şekilde azalmış; şirket borca daha az bağımlı hale gelmiş"
    if diff <= -0.05:
        return "olumlu", "hafif azalmış"
    if diff < 0.05:
        return "notr", "stabil kalmış"
    if diff < 0.3:
        return "temkinli", "hafif artmış; borç yükü büyüyor"
    return "riskli", "belirgin şekilde artmış; borç yükü hızla büyüyor"


def summarize(history: FinancialHistory) -> list[tuple[str, str]]:
    """
    Bilanço Karnesi'nden kısa, yorumlu çıkarımlar.

    Her satır (metin, etiket) döner — etiket "olumlu"/"temkinli"/"riskli"/"notr"
    (UI bunu renk/ikona çevirir). Metin şablonlar + sayısal eşiklerle DİNAMİK
    üretilir: her hissede güncel rakamlar şablona girer, elle yazılmış hisseye
    özel metin yoktur — veriler değiştiğinde (yeni çeyrek, yeniden çekme) aynı
    fonksiyon aynı mantıkla otomatik yeniden üretir.
    """
    annuals = _annuals(history)
    if len(annuals) < 2:
        return [("Trend çıkarımı için yeterli yıllık veri yok.", "notr")]

    first, last = annuals[0], annuals[-1]
    lines: list[tuple[str, str]] = []

    # Satış büyümesi (son yıl + çok yıllık CAGR)
    yoy = year_over_year(history)
    if yoy and yoy[-1].revenue_growth is not None:
        g = yoy[-1].revenue_growth
        tag, note = _growth_note(g)
        verb = "büyüdü" if g >= 0 else "daraldı"
        lines.append((f"Satış son yıl %{g * 100:+.0f} {verb} — {note}.", tag))

    if (first.revenue and last.revenue and last.revenue > 0 and first.revenue > 0
            and len(annuals) >= 3):
        n = len(annuals) - 1
        cagr = (last.revenue / first.revenue) ** (1 / n) - 1
        tag, note = _growth_note(cagr)
        lines.append((
            f"Son {n} yılda satış ortalama yıllık %{cagr * 100:+.0f} büyümüş — {note}.", tag,
        ))

    # Net kâr büyümesi
    if yoy and yoy[-1].net_income_growth is not None:
        ng = yoy[-1].net_income_growth
        tag, note = _growth_note(ng)
        verb = "arttı" if ng >= 0 else "azaldı"
        lines.append((f"Net kâr son yıl %{ng * 100:+.0f} {verb} — {note}.", tag))

    # Marj trendi
    if first.net_margin is not None and last.net_margin is not None:
        diff = last.net_margin - first.net_margin
        tag, note = _margin_note(diff)
        direction = "yükselmiş" if diff > 0 else "gerilemiş" if diff < 0 else "aynı kalmış"
        lines.append((
            f"Net kâr marjı %{first.net_margin * 100:.0f}'ten %{last.net_margin * 100:.0f}'e "
            f"{direction} — {note}.", tag,
        ))

    # Borç/özkaynak trendi
    if first.debt_to_equity is not None and last.debt_to_equity is not None:
        diff = last.debt_to_equity - first.debt_to_equity
        tag, note = _debt_note(diff)
        direction = "yükselmiş" if diff > 0 else "gerilemiş" if diff < 0 else "aynı kalmış"
        lines.append((
            f"Borç/özkaynak oranı {first.debt_to_equity:.1f}'ten {last.debt_to_equity:.1f}'e "
            f"{direction} — {note}.", tag,
        ))

    # Nakit akışı kalitesi — nakit akışı net kârı karşılıyor mu?
    if last.operating_cash_flow is not None and last.net_income and last.net_income > 0:
        ratio = last.operating_cash_flow / last.net_income
        if ratio >= 0.8:
            lines.append((
                "Faaliyetlerden gelen nakit, raporlanan net kârı karşılıyor — kâr kağıt "
                "üzerinde kalmıyor, gerçek nakde dönüşüyor (kâr kalitesi iyi).", "olumlu",
            ))
        elif ratio < 0.4:
            lines.append((
                "Faaliyetlerden gelen nakit, raporlanan net kârın belirgin altında — kârın "
                "bir kısmı henüz nakde dönüşmemiş olabilir, kâr kalitesine dikkat.", "riskli",
            ))

    return lines or [("Belirgin bir trend çıkarılamadı.", "notr")]
