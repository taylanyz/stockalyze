"""
Basit anahtar-değer deposu (cache tablosu üzerinde).

Sektör istatistikleri gibi "günde bir hesapla, sakla" verileri için.
JSON serileştirilebilir değerler tutar; TTL ile süreli.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.storage.database import Database


class KVStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> dict | list | None:
        cur = self._db.conn.execute(
            "SELECT payload, expires_at FROM cache WHERE key = ?", (f"kv:{key}",)
        )
        row = cur.fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return None
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value, ttl_hours: float = 24) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO cache (key, payload, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, "
                "expires_at=excluded.expires_at",
                (f"kv:{key}", json.dumps(value), expires),
            )

    def has_fresh(self, key: str) -> bool:
        return self.get(key) is not None
