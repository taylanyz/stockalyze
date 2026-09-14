"""
Önbellekli provider (Decorator deseni).

CachingProvider, MarketDataProvider arayüzünü uygular ama içinde
BAŞKA bir MarketDataProvider tutar ("wrapped"). Çağrıları ona iletir,
sonuçları SQLite'taki `cache` tablosunda saklar.

TTL'ler:
  - get_price_history : 4 saat  (2 yıllık bar; gün içi değişmez, en yavaş çağrı)
  - get_snapshot / get_fundamentals : 1 saat  (fiyat içerir; kısa tutuyoruz)

get_snapshot/get_fundamentals önbelleği "gün sonu / toplu tarama"
senaryosu için: 20 hisseyi günde birkaç kez çalıştırırken her seferinde
yfinance'in yavaş .info çağrısını tekrarlamamak. Tek hisseye anlık
bakışta 1 saatlik gecikme kabul edilebilir; kabul edilmezse --no-cache.

Evaluator bu sınıfı gerçek provider'dan ayırt edemez.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum

import pandas as pd

from src.models import Fundamentals, Market, StockSnapshot
from src.providers.base import MarketDataProvider
from src.storage.database import Database

HISTORY_TTL = timedelta(hours=4)
INFO_TTL = timedelta(hours=1)


def _json_default(o):
    return o.value if isinstance(o, Enum) else str(o)


class CachingProvider(MarketDataProvider):
    def __init__(
        self,
        wrapped: MarketDataProvider,
        db: Database,
        history_ttl: timedelta = HISTORY_TTL,
        info_ttl: timedelta = INFO_TTL,
    ) -> None:
        self._wrapped = wrapped
        self._db = db
        self._history_ttl = history_ttl
        self._info_ttl = info_ttl

    # ---- snapshot / fundamentals: kısa TTL --------------------------

    def get_snapshot(self, symbol: str) -> StockSnapshot:
        key = f"snapshot:{symbol.upper()}"
        cached = self._cache_get(key)
        if cached is not None:
            d = json.loads(cached)
            d["market"] = Market(d["market"])
            return StockSnapshot(**d)

        snap = self._wrapped.get_snapshot(symbol)
        self._cache_set(key, json.dumps(asdict(snap), default=_json_default), self._info_ttl)
        return snap

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        key = f"fundamentals:{symbol.upper()}"
        cached = self._cache_get(key)
        if cached is not None:
            return Fundamentals(**json.loads(cached))

        fund = self._wrapped.get_fundamentals(symbol)
        self._cache_set(key, json.dumps(asdict(fund), default=_json_default), self._info_ttl)
        return fund

    # ---- price history: uzun TTL -----------------------------------

    def get_price_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        key = f"history:{symbol.upper()}:{period}"
        cached = self._cache_get(key)
        if cached is not None:
            df = pd.read_json(io.StringIO(cached), orient="split")
            df.index = pd.to_datetime(df.index)
            return df

        df = self._wrapped.get_price_history(symbol, period)
        self._cache_set(key, df.to_json(orient="split"), self._history_ttl)
        return df

    # ---- cache tablosu yardımcıları -------------------------------

    def _cache_get(self, key: str) -> str | None:
        cur = self._db.conn.execute(
            "SELECT payload, expires_at FROM cache WHERE key = ?", (key,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            with self._db.conn:
                self._db.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            return None
        return row["payload"]

    def _cache_set(self, key: str, payload: str, ttl: timedelta) -> None:
        expires_at = (datetime.now(timezone.utc) + ttl).isoformat()
        with self._db.conn:
            self._db.conn.execute(
                "INSERT INTO cache (key, payload, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, "
                "expires_at=excluded.expires_at",
                (key, payload, expires_at),
            )

    def clear_cache(self) -> None:
        with self._db.conn:
            self._db.conn.execute("DELETE FROM cache")
