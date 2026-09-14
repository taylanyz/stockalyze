"""Yatırım günlüğü / notlar — notes tablosu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.storage.database import Database


@dataclass
class Note:
    id: int
    symbol: str
    created_at: str
    text: str


class NotesRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, symbol: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO notes (symbol, created_at, text) VALUES (?, ?, ?)",
                (symbol.upper(), datetime.now(timezone.utc).isoformat(), text),
            )

    def for_symbol(self, symbol: str) -> list[Note]:
        cur = self._db.conn.execute(
            "SELECT id, symbol, created_at, text FROM notes "
            "WHERE symbol = ? ORDER BY created_at DESC",
            (symbol.upper(),),
        )
        return [Note(**dict(r)) for r in cur.fetchall()]

    def delete(self, note_id: int) -> None:
        with self._db.conn:
            self._db.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def recent(self, limit: int = 30) -> list[Note]:
        cur = self._db.conn.execute(
            "SELECT id, symbol, created_at, text FROM notes "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [Note(**dict(r)) for r in cur.fetchall()]
