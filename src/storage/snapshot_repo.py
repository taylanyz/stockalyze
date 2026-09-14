"""
Günlük snapshot deposu (Repository deseni).

StockEvaluation nesnesini alıp daily_snapshots tablosuna yazar,
geri okurken düz sözlük (dict) döndürür. Kodun geri kalanı SQL bilmez.

Amaç: "her gün ne kaydettik" ve "dünden bugüne ne değişti" sorularına
cevap verebilmek (gün sonu değerlendirmesi buna dayanacak).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import StockEvaluation
from src.storage.database import Database

# Tabloya yazılacak sütunlar (fetched_at hariç — onu biz üretiyoruz).
_COLUMNS = [
    "symbol", "snapshot_date", "market", "name", "currency",
    "price", "previous_close", "day_change_pct", "market_cap",
    "pe_trailing", "pe_forward", "price_to_book", "profit_margin",
    "operating_margin", "return_on_equity", "debt_to_equity",
    "current_ratio", "dividend_yield",
    "tech_as_of", "last_close", "sma_50", "sma_200",
    "price_vs_sma50_pct", "price_vs_sma200_pct", "trend", "cross_signal",
    "rsi_14", "rsi_zone", "volume_ratio",
]


def _evaluation_to_row(ev: StockEvaluation, snapshot_date: str) -> dict:
    """StockEvaluation -> tabloya yazılabilir düz sözlük."""
    snap, fund, tech = ev.snapshot, ev.fundamentals, ev.technical
    row = {c: None for c in _COLUMNS}

    row["symbol"] = ev.symbol
    row["snapshot_date"] = snapshot_date

    if snap is not None:
        row.update(
            market=snap.market.value,
            name=snap.name,
            currency=snap.currency,
            price=snap.price,
            previous_close=snap.previous_close,
            day_change_pct=snap.day_change_pct,
            market_cap=snap.market_cap,
        )
    if fund is not None:
        row.update(
            pe_trailing=fund.pe_trailing,
            pe_forward=fund.pe_forward,
            price_to_book=fund.price_to_book,
            profit_margin=fund.profit_margin,
            operating_margin=fund.operating_margin,
            return_on_equity=fund.return_on_equity,
            debt_to_equity=fund.debt_to_equity,
            current_ratio=fund.current_ratio,
            dividend_yield=fund.dividend_yield,
        )
    if tech is not None:
        row.update(
            tech_as_of=tech.as_of,
            last_close=tech.last_close,
            sma_50=tech.sma_50,
            sma_200=tech.sma_200,
            price_vs_sma50_pct=tech.price_vs_sma50_pct,
            price_vs_sma200_pct=tech.price_vs_sma200_pct,
            trend=tech.trend.value,
            cross_signal=tech.cross_signal,
            rsi_14=tech.rsi_14,
            rsi_zone=tech.rsi_zone.value,
            volume_ratio=tech.volume_ratio,
        )
    return row


class SnapshotRepository:
    """daily_snapshots tablosu üzerinde okuma/yazma işlemleri."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ---- yazma ---------------------------------------------------------

    def save(self, ev: StockEvaluation, snapshot_date: str | None = None) -> None:
        """Tek bir değerlendirmeyi kaydet (aynı gün + sembol varsa üzerine yazar)."""
        self.save_many([ev], snapshot_date)

    def save_many(
        self, evaluations: list[StockEvaluation], snapshot_date: str | None = None
    ) -> int:
        """
        Birden çok değerlendirmeyi tek transaction'da kaydet.
        Değerlendirilemeyen (error dolu, snapshot yok) kayıtlar atlanır.
        Kaydedilen satır sayısını döndürür.
        """
        snapshot_date = snapshot_date or datetime.now().strftime("%Y-%m-%d")
        fetched_at = datetime.now(timezone.utc).isoformat()

        rows = [
            {**_evaluation_to_row(ev, snapshot_date), "fetched_at": fetched_at}
            for ev in evaluations
            if ev.ok  # sadece en az fiyat verisi olanlar
        ]
        if not rows:
            return 0

        cols = _COLUMNS + ["fetched_at"]
        placeholders = ", ".join(f":{c}" for c in cols)
        # UPSERT: aynı (symbol, snapshot_date) varsa günceller.
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("symbol", "snapshot_date"))
        sql = (
            f"INSERT INTO daily_snapshots ({', '.join(cols)}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(symbol, snapshot_date) DO UPDATE SET {updates}"
        )
        with self._db.conn:  # otomatik commit/rollback
            self._db.conn.executemany(sql, rows)
        return len(rows)

    # ---- okuma --------------------------------------------------------

    def get(self, symbol: str, snapshot_date: str) -> dict | None:
        """Belirli gün + sembol kaydı."""
        cur = self._db.conn.execute(
            "SELECT * FROM daily_snapshots WHERE symbol = ? AND snapshot_date = ?",
            (symbol.upper(), snapshot_date),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def previous(self, symbol: str, before_date: str) -> dict | None:
        """
        Verilen tarihten ÖNCEKI en yakın kayıt (gün sonu kıyası için).
        Dün kayıt yoksa evvelki güne düşer.
        """
        cur = self._db.conn.execute(
            "SELECT * FROM daily_snapshots "
            "WHERE symbol = ? AND snapshot_date < ? "
            "ORDER BY snapshot_date DESC LIMIT 1",
            (symbol.upper(), before_date),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def history(self, symbol: str, limit: int = 30) -> list[dict]:
        """Bir sembolün son N günlük kayıtları (yeni -> eski)."""
        cur = self._db.conn.execute(
            "SELECT * FROM daily_snapshots WHERE symbol = ? "
            "ORDER BY snapshot_date DESC LIMIT ?",
            (symbol.upper(), limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def rows_on(self, snapshot_date: str) -> list[dict]:
        """Belirli günde kaydedilmiş tüm satırlar (tam kayıt)."""
        cur = self._db.conn.execute(
            "SELECT * FROM daily_snapshots WHERE snapshot_date = ? ORDER BY symbol",
            (snapshot_date,),
        )
        return [dict(r) for r in cur.fetchall()]

    def symbols_on(self, snapshot_date: str) -> list[str]:
        """Belirli günde kaydı olan tüm semboller."""
        cur = self._db.conn.execute(
            "SELECT symbol FROM daily_snapshots WHERE snapshot_date = ? ORDER BY symbol",
            (snapshot_date,),
        )
        return [r["symbol"] for r in cur.fetchall()]

    def known_names(self) -> dict[str, str]:
        """
        Daha önce kaydedilmiş şirket adları: {sembol: ad}.
        Trend/radar listelerinde ad sütununu doldurmak için — daha önce
        değerlendirilmiş (kaydedilmiş) hisselerin adı ağa çıkmadan gelir.
        """
        cur = self._db.conn.execute(
            "SELECT symbol, name FROM daily_snapshots "
            "WHERE name IS NOT NULL GROUP BY symbol"
        )
        return {r["symbol"]: r["name"] for r in cur.fetchall()}

    def dates(self) -> list[str]:
        """Kayıt bulunan tüm günler (yeni -> eski)."""
        cur = self._db.conn.execute(
            "SELECT DISTINCT snapshot_date FROM daily_snapshots ORDER BY snapshot_date DESC"
        )
        return [r["snapshot_date"] for r in cur.fetchall()]
