"""Uyarı kuralları — alert_rules tablosu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from src.storage.database import Database

KINDS = {
    "rsi_above": "RSI şu değerin üstüne çıkınca",
    "rsi_below": "RSI şu değerin altına inince",
    "price_above": "Fiyat şu değeri geçince",
    "price_below": "Fiyat şu değerin altına inince",
    "score_below": "Puan şu değerin altına inince",
    "golden_cross": "Altın kesişim olunca (eşik yok)",
}


@dataclass
class AlertRule:
    id: int
    symbol: str
    kind: str
    threshold: float | None
    active: int
    last_fired: str | None

    def describe(self) -> str:
        base = KINDS.get(self.kind, self.kind)
        if self.threshold is not None and self.kind != "golden_cross":
            return f"{self.symbol}: {base} {self.threshold:g}"
        return f"{self.symbol}: {base}"


class AlertsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def all(self, active_only: bool = False) -> list[AlertRule]:
        q = "SELECT id, symbol, kind, threshold, active, last_fired FROM alert_rules"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY symbol, id"
        return [AlertRule(**dict(r)) for r in self._db.conn.execute(q).fetchall()]

    def add(self, symbol: str, kind: str, threshold: float | None) -> None:
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO alert_rules (symbol, kind, threshold, created_at) "
                "VALUES (?, ?, ?, ?)",
                (symbol.upper(), kind, threshold, datetime.now(timezone.utc).isoformat()),
            )

    def delete(self, rule_id: int) -> None:
        with self._db.conn:
            self._db.conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))

    def toggle(self, rule_id: int, active: bool) -> None:
        with self._db.conn:
            self._db.conn.execute(
                "UPDATE alert_rules SET active = ? WHERE id = ?", (int(active), rule_id)
            )

    def mark_fired(self, rule_id: int) -> None:
        with self._db.conn:
            self._db.conn.execute(
                "UPDATE alert_rules SET last_fired = ? WHERE id = ?",
                (date.today().isoformat(), rule_id),
            )
