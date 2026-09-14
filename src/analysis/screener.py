"""
Tarama (screener) — evreni filtre kriterlerine göre eleyip sıralar.

Saf mantık: değerlendirilmiş hisse listesi + filtreler -> sıralı sonuç.
Ağ/değerlendirme çağrısı yapmaz (onu sunum katmanı cache'ler).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.scoring import score_evaluation
from src.models import Market, StockEvaluation


@dataclass
class ScreenFilters:
    markets: set = field(default_factory=lambda: {Market.BIST, Market.US})
    min_score: int | None = None
    max_pe: float | None = None
    max_pb: float | None = None
    min_roe: float | None = None          # kesir (0.15 = %15)
    min_margin: float | None = None       # net kâr marjı, kesir
    trends: set | None = None             # {"Yükseliş", "Yatay / Karışık", ...}
    max_rsi: float | None = None
    min_dividend: float | None = None     # kesir


@dataclass
class ScreenHit:
    ev: StockEvaluation
    score: int


def _passes(ev: StockEvaluation, score: int | None, f: ScreenFilters) -> bool:
    snap, fund, tech = ev.snapshot, ev.fundamentals, ev.technical

    if snap.market not in f.markets:
        return False
    if f.min_score is not None and (score is None or score < f.min_score):
        return False

    if f.max_pe is not None:
        if fund is None or fund.pe_trailing is None or fund.pe_trailing > f.max_pe \
                or fund.pe_trailing <= 0:
            return False
    if f.max_pb is not None:
        if fund is None or fund.price_to_book is None or fund.price_to_book > f.max_pb:
            return False
    if f.min_roe is not None:
        if fund is None or fund.return_on_equity is None or fund.return_on_equity < f.min_roe:
            return False
    if f.min_margin is not None:
        if fund is None or fund.profit_margin is None or fund.profit_margin < f.min_margin:
            return False
    if f.min_dividend is not None:
        if fund is None or fund.dividend_yield is None or fund.dividend_yield < f.min_dividend:
            return False

    if f.trends:
        if tech is None or tech.trend.value not in f.trends:
            return False
    if f.max_rsi is not None:
        if tech is None or tech.rsi_14 is None or tech.rsi_14 > f.max_rsi:
            return False

    return True


def run_screener(
    evals: list[StockEvaluation],
    filters: ScreenFilters,
    sector_stats: dict | None = None,
) -> list[ScreenHit]:
    hits: list[ScreenHit] = []
    for ev in evals:
        if not ev.ok:
            continue
        sc = score_evaluation(ev, sector_stats)
        total = sc.total if sc else None
        if _passes(ev, total, filters):
            hits.append(ScreenHit(ev=ev, score=total or 0))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits
