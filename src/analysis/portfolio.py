"""
Portföy analizi — pozisyonlar + güncel değerlendirmelerden özet çıkarır.

Saf mantık: Position listesi + StockEvaluation listesi -> PortfolioSummary.
Yatırım tavsiyesi değildir; sadece mevcut durumun toplamı.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.scoring import score_evaluation
from src.models import StockEvaluation
from src.storage.portfolio_repo import Position


@dataclass
class Holding:
    symbol: str
    name: str
    currency: str | None
    quantity: float
    buy_price: float
    price: float | None
    sector: str | None
    score: int | None
    dividend_yield: float | None       # kesir

    @property
    def cost(self) -> float:
        return self.quantity * self.buy_price

    @property
    def value(self) -> float | None:
        return self.quantity * self.price if self.price is not None else None

    @property
    def pnl(self) -> float | None:
        return self.value - self.cost if self.value is not None else None

    @property
    def pnl_pct(self) -> float | None:
        return self.pnl / self.cost if (self.pnl is not None and self.cost) else None

    @property
    def est_annual_dividend(self) -> float | None:
        if self.value is None or self.dividend_yield is None:
            return None
        return self.value * self.dividend_yield


@dataclass
class PortfolioSummary:
    holdings: list[Holding] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)   # değerlendirilemeyen semboller

    # not: para birimleri karışıksa toplamlar YAKLAŞIKtır (kur çevrimi yok)
    @property
    def total_cost(self) -> float:
        return sum(h.cost for h in self.holdings)

    @property
    def total_value(self) -> float:
        return sum(h.value for h in self.holdings if h.value is not None)

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.total_cost

    @property
    def total_pnl_pct(self) -> float | None:
        return self.total_pnl / self.total_cost if self.total_cost else None

    @property
    def weighted_score(self) -> float | None:
        pairs = [(h.value, h.score) for h in self.holdings
                 if h.value and h.score is not None]
        if not pairs:
            return None
        tot = sum(v for v, _ in pairs)
        return sum(v * s for v, s in pairs) / tot if tot else None

    @property
    def est_annual_dividend(self) -> float:
        return sum(h.est_annual_dividend or 0 for h in self.holdings)

    @property
    def sector_weights(self) -> dict[str, float]:
        out: dict[str, float] = {}
        tv = self.total_value
        if not tv:
            return out
        for h in self.holdings:
            if h.value:
                out[h.sector or "Bilinmiyor"] = out.get(h.sector or "Bilinmiyor", 0) + h.value / tv
        return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))

    @property
    def currencies(self) -> set[str]:
        return {h.currency for h in self.holdings if h.currency}


def build_portfolio(
    positions: list[Position],
    evals: dict[str, StockEvaluation],
    sector_stats: dict | None = None,
) -> PortfolioSummary:
    holdings: list[Holding] = []
    missing: list[str] = []
    for p in positions:
        ev = evals.get(p.symbol)
        if ev is None or not ev.ok:
            missing.append(p.symbol)
            continue
        sc = score_evaluation(ev, sector_stats)
        f = ev.fundamentals
        holdings.append(Holding(
            symbol=p.symbol, name=ev.snapshot.name, currency=ev.snapshot.currency,
            quantity=p.quantity, buy_price=p.buy_price, price=ev.snapshot.price,
            sector=ev.snapshot.sector, score=sc.total if sc else None,
            dividend_yield=f.dividend_yield if f else None,
        ))
    return PortfolioSummary(holdings=holdings, missing=missing)
