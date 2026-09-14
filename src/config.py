"""
Proje geneli yol ve dosya-listesi yardımcıları.

app.py (CLI) ve streamlit_app.py (web) ortak kullanır.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "watchlist.txt"
BIST_UNIVERSE_PATH = ROOT / "bist100.txt"
US_UNIVERSE_PATH = ROOT / "us100.txt"


def read_symbol_file(path: Path) -> list[str]:
    """Düz metin sembol listesi oku (boş satır ve # yorumları atla, büyük harfe çevir)."""
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.upper())
    return out


def load_watchlist() -> list[str]:
    return read_symbol_file(WATCHLIST_PATH)


def load_bist_universe() -> list[str]:
    return read_symbol_file(BIST_UNIVERSE_PATH)


def load_us_universe() -> list[str]:
    return read_symbol_file(US_UNIVERSE_PATH)


def load_full_universe() -> list[str]:
    return load_bist_universe() + load_us_universe()


def save_watchlist(symbols: list[str]) -> None:
    """Sembol listesini watchlist.txt'e yaz (basit biçim, yorum korunmaz)."""
    seen: list[str] = []
    for s in symbols:
        s = s.strip().upper()
        if s and s not in seen:
            seen.append(s)
    WATCHLIST_PATH.write_text(
        "# Gün sonu değerlendirmesinde izlenecek hisseler.\n"
        "# Satır başına bir sembol. BIST için .IS uzantısı.\n\n"
        + "\n".join(seen) + "\n",
        encoding="utf-8",
    )


def add_to_watchlist(symbol: str) -> bool:
    """Sembolü watchlist'e ekle. Zaten varsa False döner."""
    symbol = symbol.strip().upper()
    current = load_watchlist()
    if not symbol or symbol in current:
        return False
    save_watchlist(current + [symbol])
    return True


def remove_from_watchlist(symbol: str) -> None:
    symbol = symbol.strip().upper()
    save_watchlist([s for s in load_watchlist() if s != symbol])
