"""
Ana sayfa trend raporu.

Watchlist'ten bağımsız: "bugün piyasada ne hareketleniyor".
  - ABD: yfinance hazır tarayıcıları
  - BIST: verilen evreni (bist30.txt) toplu indirip sıralama

İsteğe bağlı olarak listelerin ilk N hissesini puanlar (yavaş; --deep).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.scoring import score_evaluation
from src.evaluator import Evaluator
from src.providers.screener import MarketScreener, Mover


@dataclass
class TrendingReport:
    us: dict[str, list[Mover]] = field(default_factory=dict)     # gainers/losers/actives
    bist: dict[str, list[Mover]] = field(default_factory=dict)


def build_trending_report(
    screener: MarketScreener,
    bist_universe: list[str],
    *,
    count: int = 12,
    evaluator: Evaluator | None = None,
    score_top: int = 0,
    names: dict[str, str] | None = None,
) -> TrendingReport:
    """
    evaluator + score_top verilirse, her listenin ilk `score_top` hissesi
    puanlanır (Mover.score doldurulur). Aksi halde hızlı mod (puansız).
    names: {sembol: ad} — ad'ı yalnızca sembolden türetilmiş satırlara uygula.
    """
    report = TrendingReport(
        us={
            "gainers": screener.us_movers("gainers", count),
            "losers": screener.us_movers("losers", count),
            "actives": screener.us_movers("actives", count),
        },
        bist=screener.bist_movers(bist_universe, top=count),
    )

    if names:
        for group in (report.us, report.bist):
            for movers in group.values():
                for m in movers:
                    if m.name in (m.symbol, m.symbol.removesuffix(".IS")):
                        m.name = names.get(m.symbol, m.name)

    if evaluator is not None and score_top > 0:
        _attach_scores(report, evaluator, score_top)

    return report


_MAX_SCORED = 20   # --deep'te toplam puanlanacak sembol tavanı (hız için)


def _attach_scores(report: TrendingReport, evaluator: Evaluator, n: int) -> None:
    # Aynı sembolü iki kez değerlendirmemek için topla.
    targets: set[str] = set()
    for group in (report.us, report.bist):
        for movers in group.values():
            for m in movers[:n]:
                targets.add(m.symbol)
    if len(targets) > _MAX_SCORED:
        targets = set(sorted(targets)[:_MAX_SCORED])

    scores: dict[str, int] = {}
    names: dict[str, str] = {}
    for ev in evaluator.evaluate_many(sorted(targets)):
        if ev.snapshot and ev.snapshot.name:
            names[ev.symbol] = ev.snapshot.name
        s = score_evaluation(ev)
        if s is not None:
            scores[ev.symbol] = s.total

    for group in (report.us, report.bist):
        for movers in group.values():
            for m in movers:
                m.score = scores.get(m.symbol)
                if m.symbol in names and m.name in (m.symbol, m.symbol.removesuffix(".IS")):
                    m.name = names[m.symbol]
