"""
Basit, ŞEFFAF puanlama.

Kara kutu değil: her puan bir gerekçeyle geliyor (ScoreReason).
Toplam = 50 (nötr taban) + temel katkı + teknik katkı, 0-100'e kırpılır.

ÖNEMLİ: Bu puan yatırım tavsiyesi değildir. Sadece "hangi hisseye
önce bakayım" elemesini hızlandıran kaba bir sıralama aracıdır.
Eşikler sabittir ve tartışmaya açıktır; sektör ortalamasına göre
görecelilik ileride eklenebilir.

Girdi olarak DÜZ bir sözlük (metrics) alır. Anahtarlar bilerek
veritabanı sütun adlarıyla aynı — böylece hem canlı değerlendirmeyi
hem de kayıtlı geçmiş satırını aynı fonksiyonla puanlayabiliyoruz
(gün sonu kıyası bunu kullanıyor).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from src.models import Market, StockEvaluation

BASE = 50


@dataclass
class ScoreReason:
    label: str
    points: int
    category: str          # "Temel" veya "Teknik"


@dataclass
class Score:
    total: int
    fundamental: int       # taban hariç temel katkı (+/-)
    technical: int         # taban hariç teknik katkı (+/-)
    reasons: list[ScoreReason] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.total >= 70:
            return "Yakından bakmaya değer"
        if self.total >= 45:
            return "Nötr / karışık"
        return "Şimdilik zayıf görünüyor"


# --- eşikler: piyasaya göre farklı --------------------------------------
# (BIST'te F/K ve PD/DD çarpanları yapısal olarak ABD'den düşük;
#  aynı eşiği kullanmak yanıltıcı olur.)

_PE_BANDS = {
    Market.US:   [(15, 15), (25, 8), (40, 0), (float("inf"), -8)],
    Market.BIST: [(6, 15), (10, 8), (15, 0), (float("inf"), -8)],
}
_PB_BANDS = {
    Market.US:   [(3, 8), (6, 0), (float("inf"), -5)],
    Market.BIST: [(1.5, 8), (3, 0), (float("inf"), -5)],
}


def _band_points(value: float | None, bands: list[tuple[float, int]]) -> int | None:
    """Değer hangi banda düşüyorsa o puanı döndür. None ise None (puan yok)."""
    if value is None:
        return None
    for upper, pts in bands:
        if value <= upper:
            return pts
    return bands[-1][1]


def _get(m: Mapping, key: str) -> float | None:
    v = m.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _relative_points(value: float, median: float, *, cheap_pts: int, exp_pts: int) -> tuple[int, str]:
    """Değeri sektör medyanına göre puanla. (puan, etiket)"""
    r = value / median if median else None
    if r is None:
        return 0, "sektör verisi yok"
    if r <= 0.7:
        return cheap_pts, f"sektör medyanının %{(1 - r) * 100:.0f} altında (ucuz)"
    if r <= 1.3:
        return 0, "sektör medyanına yakın"
    return exp_pts, f"sektör medyanının %{(r - 1) * 100:.0f} üstünde (pahalı)"


def score_metrics(metrics: Mapping, market: Market, sector_stats: dict | None = None) -> Score:
    """
    Düz metrik sözlüğünü puana çevir.

    sector_stats verilir + hissenin sektörü tanınırsa: F/K ve PD/DD
    sektör medyanına göre puanlanır. Aksi halde mutlak eşikler kullanılır.
    """
    reasons: list[ScoreReason] = []

    def add(label: str, pts: int | None, category: str) -> None:
        if pts:  # 0 ve None eklenmez (gürültü olmasın)
            reasons.append(ScoreReason(label, pts, category))

    sector = metrics.get("sector")
    sec_med = None
    if sector_stats and sector:
        sec_med = (sector_stats.get("sectors") or {}).get(sector)

    # ---- TEMEL ------------------------------------------------------
    pe = _get(metrics, "pe_trailing")
    if pe is not None:
        if sec_med and sec_med.get("pe_median"):
            pts, note = _relative_points(pe, sec_med["pe_median"], cheap_pts=15, exp_pts=-8)
            add(f"F/K {pe:.1f} — {note}", pts, "Temel")
        else:
            pe_pts = _band_points(pe, _PE_BANDS[market])
            add(f"F/K {pe:.1f}" + (" (ucuz)" if pe_pts and pe_pts > 0 else
                " (pahalı)" if pe_pts and pe_pts < 0 else " (orta)"), pe_pts, "Temel")

    pb = _get(metrics, "price_to_book")
    if pb is not None:
        if sec_med and sec_med.get("pb_median"):
            pts, note = _relative_points(pb, sec_med["pb_median"], cheap_pts=8, exp_pts=-5)
            add(f"PD/DD {pb:.1f} — {note}", pts, "Temel")
        else:
            pb_pts = _band_points(pb, _PB_BANDS[market])
            add(f"PD/DD {pb:.1f}" + (" (düşük)" if pb_pts and pb_pts > 0 else
                " (yüksek)" if pb_pts and pb_pts < 0 else ""), pb_pts, "Temel")

    pm = _get(metrics, "profit_margin")
    if pm is not None:
        pts = 10 if pm > 0.20 else 5 if pm > 0.10 else 0 if pm >= 0 else -10
        add(f"Net marj %{pm * 100:.0f}", pts, "Temel")

    roe = _get(metrics, "return_on_equity")
    if roe is not None:
        pts = 10 if roe > 0.20 else 5 if roe > 0.10 else 0 if roe >= 0 else -8
        add(f"ROE %{roe * 100:.0f}", pts, "Temel")

    de = _get(metrics, "debt_to_equity")
    if de is not None:
        pts = 5 if de < 1 else 0 if de <= 2 else -8
        add(f"Borç/Özkaynak {de:.1f}", pts, "Temel")

    cr = _get(metrics, "current_ratio")
    if cr is not None:
        pts = 3 if cr > 1.5 else 0 if cr >= 1 else -5
        add(f"Cari oran {cr:.2f}", pts, "Temel")

    # ---- TEKNİK ---------------------------------------------------
    trend = metrics.get("trend")
    trend_pts = {"Yükseliş": 15, "Düşüş": -15}.get(trend, 0)
    if trend:
        add(f"Trend: {trend}", trend_pts, "Teknik")

    vs200 = _get(metrics, "price_vs_sma200_pct")
    if vs200 is not None:
        pts = 5 if vs200 > 0 else -5 if vs200 < -10 else 0
        add(f"Fiyat SMA200'e göre %{vs200:+.0f}", pts, "Teknik")

    cross = metrics.get("cross_signal")
    if cross:
        # "Altın kesişim (12 gün önce)" -> gün sayısını ayıkla
        recent = _days_ago(cross) is not None and _days_ago(cross) <= 25
        if "Altın" in cross:
            add(cross, 10 if recent else 4, "Teknik")
        elif "Ölüm" in cross:
            add(cross, -10 if recent else -4, "Teknik")

    rsi = _get(metrics, "rsi_14")
    if rsi is not None:
        if rsi >= 70:
            add(f"RSI {rsi:.0f} (aşırı alım)", -8, "Teknik")
        elif rsi <= 30:
            add(f"RSI {rsi:.0f} (aşırı satım)", 5, "Teknik")
        elif 40 <= rsi <= 60:
            add(f"RSI {rsi:.0f} (sağlıklı)", 3, "Teknik")

    vol = _get(metrics, "volume_ratio")
    if vol is not None:
        if vol > 1.5:
            add(f"Hacim ortalamanın {vol:.1f}x'i", 3, "Teknik")
        elif vol < 0.5:
            add(f"Hacim zayıf ({vol:.1f}x)", -2, "Teknik")

    fundamental = sum(r.points for r in reasons if r.category == "Temel")
    technical = sum(r.points for r in reasons if r.category == "Teknik")
    total = max(0, min(100, BASE + fundamental + technical))

    reasons.sort(key=lambda r: r.points, reverse=True)
    return Score(total=total, fundamental=fundamental, technical=technical, reasons=reasons)


def _days_ago(cross_signal: str) -> int | None:
    """'Altın kesişim (12 gün önce)' -> 12"""
    import re

    m = re.search(r"\((\d+)\s*gün", cross_signal)
    return int(m.group(1)) if m else None


def metrics_from_evaluation(ev: StockEvaluation) -> dict:
    """
    StockEvaluation -> puanlama için düz metrik sözlüğü.
    Anahtarlar veritabanı sütunlarıyla aynı (kayıtlı satır da puanlanabilsin).
    """
    snap, fund, tech = ev.snapshot, ev.fundamentals, ev.technical
    m: dict = {}
    if snap is not None and snap.sector:
        m["sector"] = snap.sector
    if fund is not None:
        m.update(
            pe_trailing=fund.pe_trailing,
            price_to_book=fund.price_to_book,
            profit_margin=fund.profit_margin,
            return_on_equity=fund.return_on_equity,
            debt_to_equity=fund.debt_to_equity,
            current_ratio=fund.current_ratio,
        )
    if tech is not None:
        m.update(
            price_vs_sma200_pct=tech.price_vs_sma200_pct,
            trend=tech.trend.value,
            cross_signal=tech.cross_signal,
            rsi_14=tech.rsi_14,
            volume_ratio=tech.volume_ratio,
        )
    return m


def score_evaluation(ev: StockEvaluation, sector_stats: dict | None = None) -> Score | None:
    """Canlı bir değerlendirmeyi puanla. Piyasa bilinmiyorsa None."""
    if ev.snapshot is None:
        return None
    return score_metrics(metrics_from_evaluation(ev), ev.snapshot.market, sector_stats)
