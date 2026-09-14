"""
Gün sonu değerlendirmesi.

Bugün çekilen değerlendirmeleri, veritabanındaki BİR ÖNCEKİ kayıtla
karşılaştırır ve "ne değişti" özeti üretir:
  - puan değişimi (skor kaç puan arttı/azaldı)
  - yeni teknik sinyaller (trend döndü, altın/ölüm kesişimi, RSI aşırı bölge)

Saf mantık: girdi = değerlendirmeler + repo, çıktı = EodReport.
Ekrana basmak app.py'nin işi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.analysis.scoring import metrics_from_evaluation, score_evaluation, score_metrics
from src.models import Market, StockEvaluation
from src.storage.snapshot_repo import SnapshotRepository


@dataclass
class EodChange:
    symbol: str
    name: str
    market: Market
    price: float | None
    day_change_pct: float | None
    score_now: int
    score_prev: int | None
    prev_date: str | None
    currency: str | None = None
    new_signals: list[str] = field(default_factory=list)

    @property
    def score_delta(self) -> int | None:
        return None if self.score_prev is None else self.score_now - self.score_prev


@dataclass
class EodReport:
    date: str
    changes: list[EodChange]
    failed: list[tuple[str, str]]

    @property
    def with_signals(self) -> list[EodChange]:
        return [c for c in self.changes if c.new_signals]


def _rsi_zone(rsi: float | None) -> str | None:
    if rsi is None:
        return None
    if rsi >= 70:
        return "aşırı alım"
    if rsi <= 30:
        return "aşırı satım"
    return "nötr"


def _signals_between(new: dict, old: dict | None) -> list[str]:
    """
    İki 'metrik sözlüğü' arasındaki dikkat çekici farklar.
    Anahtarlar: trend, rsi_14, cross_signal, price_vs_sma200_pct.
    Hem canlı değerlendirme (metrics_from_evaluation) hem kayıtlı
    daily_snapshots satırı bu şekli taşır.
    """
    signals: list[str] = []

    # 1) Son 2 gün içinde gerçekleşmiş kesişim (taze sinyal).
    cross = new.get("cross_signal")
    if cross:
        m = re.search(r"\((\d+)\s*gün", cross)
        if m and int(m.group(1)) <= 2:
            signals.append(f"Yeni {cross}")

    if old is None:
        return signals

    # 2) Trend yön değişimi.
    if old.get("trend") and new.get("trend") and old["trend"] != new["trend"]:
        signals.append(f"Trend değişti: {old['trend']} → {new['trend']}")

    # 3) RSI aşırı bölgeye giriş/çıkış.
    prev_zone, now_zone = _rsi_zone(old.get("rsi_14")), _rsi_zone(new.get("rsi_14"))
    if prev_zone and now_zone and prev_zone != now_zone:
        rsi = new.get("rsi_14") or 0
        if now_zone != "nötr":
            signals.append(f"RSI {now_zone} bölgesine girdi ({rsi:.0f})")
        else:
            signals.append(f"RSI {prev_zone} bölgesinden çıktı ({rsi:.0f})")

    # 4) Fiyatın 200 günlük ortalamaya göre taraf değiştirmesi.
    pv, nv = old.get("price_vs_sma200_pct"), new.get("price_vs_sma200_pct")
    if pv is not None and nv is not None:
        if pv < 0 <= nv:
            signals.append("Fiyat SMA200'ün üstüne çıktı")
        elif pv >= 0 > nv:
            signals.append("Fiyat SMA200'ün altına indi")

    return signals


def _detect_new_signals(ev: StockEvaluation, prev: dict | None) -> list[str]:
    if ev.technical is None:
        return []
    return _signals_between(metrics_from_evaluation(ev), prev)


def build_eod_report(
    evaluations: list[StockEvaluation],
    repo: SnapshotRepository,
    date: str,
) -> EodReport:
    """
    date: bugünün tarihi (YYYY-MM-DD). Kıyas bu tarihten ÖNCEKI en yakın kayda.
    NOT: Bu fonksiyonu çağırmadan ÖNCE bugünün snapshot'ı kaydedilmiş olmalı
    (previous() zaten date'ten küçük tarihlere bakar, çakışma olmaz).
    """
    changes: list[EodChange] = []
    failed = [(e.symbol, e.error or "bilinmeyen hata") for e in evaluations if not e.ok]

    for ev in evaluations:
        if not ev.ok:
            continue

        score_now = score_evaluation(ev)
        prev = repo.previous(ev.symbol, date)
        score_prev = None
        if prev is not None:
            score_prev = score_metrics(prev, ev.snapshot.market).total

        changes.append(
            EodChange(
                symbol=ev.symbol,
                name=ev.snapshot.name,
                market=ev.snapshot.market,
                price=ev.snapshot.price,
                day_change_pct=ev.snapshot.day_change_pct,
                score_now=score_now.total if score_now else 0,
                score_prev=score_prev,
                prev_date=prev["snapshot_date"] if prev else None,
                currency=ev.snapshot.currency,
                new_signals=_detect_new_signals(ev, prev),
            )
        )

    return EodReport(date=date, changes=_sorted(changes), failed=failed)


def _sorted(changes: list[EodChange]) -> list[EodChange]:
    """Önce sinyali olanlar, sonra puan değişimi büyük olanlar."""
    return sorted(
        changes,
        key=lambda c: (
            bool(c.new_signals),
            abs(c.score_delta) if c.score_delta is not None else 0,
        ),
        reverse=True,
    )


@dataclass
class FeedEntry:
    date: str
    symbol: str
    text: str


def change_feed(repo: SnapshotRepository, limit: int = 60) -> list[FeedEntry]:
    """
    Tüm ardışık snapshot günlerini kıyaslayıp kayda değer değişimleri
    tek bir zaman çizelgesine dizer (yeni -> eski).
    """
    dates = sorted(repo.dates())          # eski -> yeni
    entries: list[FeedEntry] = []
    for old_d, new_d in zip(dates, dates[1:]):
        report = diff_stored(repo, new_d, old_d)
        for c in report.changes:
            for s in c.new_signals:
                entries.append(FeedEntry(new_d, c.symbol, s))
            if c.score_delta is not None and abs(c.score_delta) >= 5:
                yon = "arttı" if c.score_delta > 0 else "düştü"
                entries.append(FeedEntry(
                    new_d, c.symbol, f"puan {c.score_prev}→{c.score_now} ({yon})"
                ))
    entries.sort(key=lambda e: e.date, reverse=True)
    return entries[:limit]


def diff_stored(repo: SnapshotRepository, date_new: str, date_old: str) -> EodReport:
    """
    Veritabanındaki İKİ kayıtlı günü karşılaştır — ağ yok.
    Snapshot & Değişim sayfası bunu kullanır.
    """
    new_rows = {r["symbol"]: r for r in repo.rows_on(date_new)}
    old_rows = {r["symbol"]: r for r in repo.rows_on(date_old)}

    changes: list[EodChange] = []
    for sym, new in new_rows.items():
        old = old_rows.get(sym)
        try:
            market = Market(new.get("market") or "US")
        except ValueError:
            market = Market.US
        changes.append(
            EodChange(
                symbol=sym,
                name=new.get("name") or sym,
                market=market,
                price=new.get("price"),
                day_change_pct=new.get("day_change_pct"),
                score_now=score_metrics(new, market).total,
                score_prev=score_metrics(old, market).total if old else None,
                prev_date=date_old,
                currency=new.get("currency"),
                new_signals=_signals_between(new, old),
            )
        )
    return EodReport(date=date_new, changes=_sorted(changes), failed=[])
