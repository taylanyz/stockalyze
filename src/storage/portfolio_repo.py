"""Portföy pozisyonları — positions tablosu CRUD."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.storage.database import Database


@dataclass
class Position:
    symbol: str
    quantity: float
    buy_price: float
    buy_date: str | None
    note: str | None


class PortfolioRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def all(self) -> list[Position]:
        cur = self._db.conn.execute(
            "SELECT symbol, quantity, buy_price, buy_date, note "
            "FROM positions ORDER BY symbol"
        )
        return [Position(**dict(r)) for r in cur.fetchall()]

    def upsert(self, pos: Position) -> None:
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO positions (symbol, quantity, buy_price, buy_date, note, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity, "
                "buy_price=excluded.buy_price, buy_date=excluded.buy_date, note=excluded.note",
                (pos.symbol.upper(), pos.quantity, pos.buy_price, pos.buy_date,
                 pos.note, datetime.now(timezone.utc).isoformat()),
            )

    def delete(self, symbol: str) -> None:
        with self._db.conn:
            self._db.conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol.upper(),))

    def symbols(self) -> list[str]:
        return [p.symbol for p in self.all()]
