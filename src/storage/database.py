"""
SQLite bağlantısı ve şema.

Tek sorumluluk: veritabanı dosyasını açmak ve tabloların var olduğunu
garanti etmek. İş mantığı yok — onu repository'ler yapar.

Neden SQLite: tek dosya, sunucu kurulumu yok, Python'da yerleşik (sqlite3).
Bu ölçekteki bir masaüstü araç için fazlasıyla yeterli.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Proje kökü altında data/ klasörü. .gitignore'da.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "hisse.db"

# Şema. "IF NOT EXISTS" sayesinde her açılışta güvenle çalıştırılabilir.
# (Basit bir yaklaşım; ileride sütun eklemek gerekirse hafif bir
#  migration mekanizması ekleriz.)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    symbol              TEXT NOT NULL,
    snapshot_date       TEXT NOT NULL,   -- YYYY-MM-DD, kaydı aldığımız gün
    market              TEXT,
    name                TEXT,
    currency            TEXT,

    price               REAL,
    previous_close      REAL,
    day_change_pct      REAL,
    market_cap          REAL,

    pe_trailing         REAL,
    pe_forward          REAL,
    price_to_book       REAL,
    profit_margin       REAL,
    operating_margin    REAL,
    return_on_equity    REAL,
    debt_to_equity      REAL,
    current_ratio       REAL,
    dividend_yield      REAL,

    tech_as_of          TEXT,
    last_close          REAL,
    sma_50              REAL,
    sma_200             REAL,
    price_vs_sma50_pct  REAL,
    price_vs_sma200_pct REAL,
    trend               TEXT,
    cross_signal        TEXT,
    rsi_14              REAL,
    rsi_zone            TEXT,
    volume_ratio        REAL,

    fetched_at          TEXT NOT NULL,   -- ISO zaman damgası
    PRIMARY KEY (symbol, snapshot_date)
);

CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,           -- JSON
    expires_at  TEXT NOT NULL            -- ISO zaman damgası
);

CREATE TABLE IF NOT EXISTS positions (
    symbol      TEXT PRIMARY KEY,
    quantity    REAL NOT NULL,
    buy_price   REAL NOT NULL,           -- birim maliyet (hissenin para biriminde)
    buy_date    TEXT,                    -- YYYY-MM-DD
    note        TEXT,
    added_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    created_at  TEXT NOT NULL,           -- ISO
    text        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_symbol ON notes(symbol);

CREATE TABLE IF NOT EXISTS alert_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    kind        TEXT NOT NULL,           -- rsi_above / rsi_below / price_above /
                                         -- price_below / score_below / golden_cross
    threshold   REAL,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    last_fired  TEXT                     -- ISO; aynı gün tekrar tetiklenmesin
);
CREATE INDEX IF NOT EXISTS idx_alert_symbol ON alert_rules(symbol);
"""


class Database:
    """SQLite bağlantısını yönetir; context manager olarak kullanılır."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: ileride arayüz farklı thread'den çağırırsa
        # sorun çıkmasın (şimdilik tek thread).
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        # Satırlara sözlük gibi erişim: row["price"]
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()
