"""
Uyarı kontrolü — kuralları güncel değerlendirmelerle karşılaştırır.

Saf mantık: kural + StockEvaluation -> tetiklendi mi.
`check_alerts` ağ çağrısı yapmaz; değerlendirmeleri dışarıdan alır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from src.analysis.scoring import score_evaluation
from src.models import StockEvaluation
from src.storage.alerts_repo import AlertRule


@dataclass
class TriggeredAlert:
    rule_id: int
    symbol: str
    message: str


def _rule_triggered(rule: AlertRule, ev: StockEvaluation, sector_stats=None) -> str | None:
    snap, tech = ev.snapshot, ev.technical
    k, thr = rule.kind, rule.threshold

    if k == "price_above" and snap.price is not None and thr is not None:
        return f"fiyat {snap.price:.2f} — '{thr:g} üstü' kuralı" if snap.price >= thr else None
    if k == "price_below" and snap.price is not None and thr is not None:
        return f"fiyat {snap.price:.2f} — '{thr:g} altı' kuralı" if snap.price <= thr else None

    if k in ("rsi_above", "rsi_below") and tech and tech.rsi_14 is not None and thr is not None:
        if k == "rsi_above" and tech.rsi_14 >= thr:
            return f"RSI {tech.rsi_14:.0f} — '{thr:g} üstü' kuralı"
        if k == "rsi_below" and tech.rsi_14 <= thr:
            return f"RSI {tech.rsi_14:.0f} — '{thr:g} altı' kuralı"
        return None

    if k == "score_below" and thr is not None:
        sc = score_evaluation(ev, sector_stats)
        if sc and sc.total < thr:
            return f"puan {sc.total} — '{thr:g} altı' kuralı"
        return None

    if k == "golden_cross" and tech and tech.cross_signal and "Altın" in tech.cross_signal:
        m = re.search(r"\((\d+)\s*gün", tech.cross_signal)
        if m and int(m.group(1)) <= 3:
            return f"{tech.cross_signal}"
        return None

    return None


def check_alerts(
    rules: list[AlertRule],
    evals: dict[str, StockEvaluation],
    sector_stats=None,
) -> list[TriggeredAlert]:
    """Aktif kuralları kontrol et. Aynı gün zaten tetiklenmişleri atla."""
    today = date.today().isoformat()
    out: list[TriggeredAlert] = []
    for rule in rules:
        if not rule.active or rule.last_fired == today:
            continue
        ev = evals.get(rule.symbol)
        if ev is None or not ev.ok:
            continue
        msg = _rule_triggered(rule, ev, sector_stats)
        if msg:
            out.append(TriggeredAlert(rule.id, rule.symbol, msg))
    return out
