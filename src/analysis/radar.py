"""
Radar — "bugünlerde skoru iyi + ilgi gören + trendi belli" hisseler.

Fikir:
  1. Bir evren topla (BIST 30 + ABD'nin en aktifleri + watchlist).
  2. Hepsinin geçmişini TEK bulk indirmeyle çek, trend/RSI/hacmi yerelde hesapla.
  3. "İlgi puanı" (hacim artışı + günlük/haftalık hareket) hesapla.
  4. En çok ilgi görenleri tam değerlendir (temel + puan).
  5. Trende göre bir "konumlanma notu" ekle:
       - alıcı bakışı:  düşüş trendi -> girişte fiyat düşüş riski
       - watchlist bakışı: yükseliş + aşırı alım -> geri çekilme riski

ÖNEMLİ: Notlar göstergelerin NE SÖYLEDİĞİNİ tarif eder; al/sat talimatı
değildir. Yatırım tavsiyesi değildir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.analysis.scoring import score_evaluation
from src.analysis.technical import compute_technical, describe_trend
from src.evaluator import Evaluator
from src.models import Market, RSIZone, TechnicalIndicators, Trend
from src.providers.screener import MarketScreener
from src.providers.yfinance_provider import detect_market


@dataclass
class RadarRow:
    symbol: str
    name: str
    market: Market
    price: float | None
    day_change_pct: float | None
    ret_5d_pct: float | None
    trend: Trend
    rsi_14: float | None
    rsi_zone: RSIZone
    volume_ratio: float | None
    attention: int           # 0-100 "ilgi" ölçüsü
    score: int | None        # tam değerlendirme yapıldıysa
    note: str                # konumlanma notu (kısa)
    tag: str                 # olumlu | temkinli | riskli | notr
    trend_reason: list[str]  # trendin gerekçesi, madde madde
    in_watchlist: bool


@dataclass
class RadarReport:
    hot: list[RadarRow] = field(default_factory=list)          # watchlist DIŞI, öne çıkanlar
    watchlist: list[RadarRow] = field(default_factory=list)    # senin listendekiler


# --- konumlanma notu ---------------------------------------------------

def positioning_note(tech: TechnicalIndicators, *, holding: bool) -> tuple[str, str]:
    """
    (not, etiket) döndürür. holding=True ise 'elde tutan' bakışı,
    False ise 'almayı düşünen' bakışı.
    """
    prefix = ""
    if tech.cross_signal and "gün önce" in tech.cross_signal:
        days = tech.cross_signal.split("(")[-1].split("gün")[0].strip()
        if days.isdigit() and int(days) <= 3:
            prefix = ("Yeni altın kesişim; " if "Altın" in tech.cross_signal
                      else "Yeni ölüm kesişimi; ")

    trend = tech.trend
    overbought = tech.rsi_zone is RSIZone.OVERBOUGHT
    oversold = tech.rsi_zone is RSIZone.OVERSOLD

    if trend is Trend.DOWN:
        if holding:
            return prefix + "Düşüş trendi — zayıflık sinyali", "riskli"
        return prefix + "Düşüş trendinde — girişte fiyatın daha düşme riski", "riskli"

    if trend is Trend.UP:
        if overbought:
            msg = ("Yükseliş sürüyor ama RSI aşırı alımda — kısa vadeli geri çekilme riski"
                   if holding else
                   "Yükseliş güçlü ama RSI aşırı alımda — girişte tepe riski")
            return prefix + msg, "temkinli"
        if oversold:
            return prefix + "Yükseliş trendinde, RSI düşük — dip denemesi olabilir", "olumlu"
        return prefix + "Yükseliş trendi, momentum sağlıklı", "olumlu"

    if trend is Trend.SIDEWAYS:
        return prefix + "Yatay seyir — belirgin yön yok", "notr"

    return prefix + "Trend belirsiz (yeterli geçmiş veri yok)", "notr"


# --- ilgi puanı ------------------------------------------------------

def _attention(volume_ratio: float | None, day_change_pct: float | None,
               ret_5d_pct: float | None) -> int:
    score = 0.0
    if volume_ratio:
        score += max(0.0, min(50.0, (volume_ratio - 1.0) * 40))   # 1x→0, 2.25x→50
    if day_change_pct is not None:
        score += min(30.0, abs(day_change_pct) * 4)                # ±7.5%+ → 30
    if ret_5d_pct is not None:
        score += min(20.0, abs(ret_5d_pct) * 1.5)                  # ±13%+ → 20
    return int(round(max(0.0, min(100.0, score))))


def _ret_5d(df: pd.DataFrame) -> float | None:
    closes = df["Close"].dropna()
    if len(closes) < 6:
        return None
    old, new = closes.iloc[-6], closes.iloc[-1]
    return (new - old) / old * 100 if old else None


# --- rapor kurulumu ------------------------------------------------

def build_radar(
    screener: MarketScreener,
    evaluator: Evaluator,
    universe: list[str],
    watchlist: list[str],
    *,
    include_us_actives: bool = True,
    per_market_score: int = 14,
    names: dict[str, str] | None = None,
    sector_stats: dict | None = None,
) -> RadarReport:
    names = names or {}
    watch = {s.upper() for s in watchlist}
    symbols = set(universe) | watch

    if include_us_actives:
        for kind in ("actives", "gainers"):
            for m in screener.us_movers(kind, 15):
                symbols.add(m.symbol)

    histories = screener.bulk_history(sorted(symbols), period="1y")

    # 1) Hafif geçiş: herkes için trend/RSI/hacim/ilgi.
    prelim: list[RadarRow] = []
    for sym, df in histories.items():
        tech = compute_technical(sym, df)
        ret5 = _ret_5d(df)
        att = _attention(tech.volume_ratio, _last_change(df), ret5)
        holding = sym in watch
        note, tag = positioning_note(tech, holding=holding)
        prelim.append(RadarRow(
            symbol=sym,
            name=names.get(sym, sym.removesuffix(".IS")),
            market=detect_market(sym),
            price=tech.last_close,
            day_change_pct=_last_change(df),
            ret_5d_pct=ret5,
            trend=tech.trend,
            rsi_14=tech.rsi_14,
            rsi_zone=tech.rsi_zone,
            volume_ratio=tech.volume_ratio,
            attention=att,
            score=None,
            note=note,
            tag=tag,
            trend_reason=describe_trend(tech),
            in_watchlist=holding,
        ))

    # 2) Tam değerlendirme: watchlist'in tamamı + HER PİYASADAN en çok
    #    ilgi gören N (BIST, ABD'nin yüksek oynaklığında ezilmesin diye ayrı ayrı).
    non_watch = [r for r in prelim if not r.in_watchlist]
    to_score: set[str] = set(watch)
    for mk in (Market.BIST, Market.US):
        ranked = sorted(
            [r for r in non_watch if r.market is mk],
            key=lambda r: r.attention, reverse=True,
        )
        to_score |= {r.symbol for r in ranked[:per_market_score]}
    if to_score:
        by_symbol = {r.symbol: r for r in prelim}
        for ev in evaluator.evaluate_many(sorted(to_score)):
            row = by_symbol.get(ev.symbol)
            sc = score_evaluation(ev, sector_stats)
            if row is not None and sc is not None:
                row.score = sc.total
                if ev.snapshot and ev.snapshot.name:
                    row.name = ev.snapshot.name

    # 3) Böl + sırala.
    hot = sorted(
        [r for r in prelim if not r.in_watchlist and r.score is not None],
        key=lambda r: (r.score, r.attention), reverse=True,
    )
    watch_rows = sorted(
        [r for r in prelim if r.in_watchlist],
        key=lambda r: (r.score or -1), reverse=True,
    )
    return RadarReport(hot=hot, watchlist=watch_rows)


def _last_change(df: pd.DataFrame) -> float | None:
    closes = df["Close"].dropna()
    if len(closes) < 2:
        return None
    last, prev = closes.iloc[-1], closes.iloc[-2]
    return (last - prev) / prev * 100 if prev else None
