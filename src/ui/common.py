"""
Streamlit sayfalarının ortak altyapısı.

Buradaki fikir: sayfalar İNCE kalsın. Ağır iş (veri çekme, hesaplama)
zaten src/analysis, src/evaluator, src/providers içinde. Bu modül sadece:
  - cache'li tekil kaynaklar (DB, provider, evaluator, screener)
  - cache'li veri fonksiyonları (değerlendir, trend raporu)
  - küçük biçimlendirme yardımcıları
sağlar. Web'e özgü hiçbir iş mantığı YOK.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.analysis.eod import EodReport, build_eod_report, diff_stored
from src.analysis.radar import RadarReport, build_radar
from src.analysis.scoring import Score, score_evaluation
from src.analysis.sector import _KEY as _SECTOR_KEY
from src.analysis.sector import build_sector_stats
from src.analysis.trending import TrendingReport, build_trending_report
from src.config import load_bist_universe, load_full_universe, load_watchlist
from src.storage.kv_store import KVStore
from src.evaluator import Evaluator
from src.models import StockEvaluation
from src.providers.factory import build_provider
from src.providers.news import NewsItem, NewsProvider
from src.providers.screener import MarketScreener
from src.providers.statements import StatementsProvider
from src.storage.database import Database
from src.storage.snapshot_repo import SnapshotRepository

DISCLAIMER = (
    "⚠️ Bu araç ve puanları **yatırım tavsiyesi değildir**; yalnızca araştırma "
    "amaçlıdır. Veriler üçüncü taraf kaynaklardan gelir, hatalı/gecikmeli olabilir."
)


# --- cache'li tekil kaynaklar (uygulama ömrü boyunca tek örnek) --------

@st.cache_resource
def get_db() -> Database:
    return Database()


@st.cache_resource
def get_evaluator() -> Evaluator:
    return Evaluator(build_provider(get_db()))


@st.cache_resource
def get_screener() -> MarketScreener:
    return MarketScreener()


@st.cache_resource
def get_news() -> NewsProvider:
    return NewsProvider()


def get_repo() -> SnapshotRepository:
    return SnapshotRepository(get_db())


def get_kv() -> KVStore:
    return KVStore(get_db())


def get_portfolio_repo():
    from src.storage.portfolio_repo import PortfolioRepository
    return PortfolioRepository(get_db())


def get_notes_repo():
    from src.storage.notes_repo import NotesRepository
    return NotesRepository(get_db())


def get_alerts_repo():
    from src.storage.alerts_repo import AlertsRepository
    return AlertsRepository(get_db())


def check_pending_alerts():
    """Aktif uyarı kurallarını kontrol et — (tetiklenenler, repo)."""
    from src.analysis.alerts import check_alerts

    repo = get_alerts_repo()
    rules = repo.all(active_only=True)
    if not rules:
        return [], repo
    syms = tuple(sorted({r.symbol for r in rules}))
    evals = {e.symbol: e for e in evaluate(syms)}
    return check_alerts(rules, evals, sector_stats()), repo


@st.cache_data(ttl=1800, show_spinner=False)
def sector_stats() -> dict | None:
    """Kayıtlı sektör medyanları (yoksa None -> skorlama mutlak eşiklere düşer)."""
    return get_kv().get(_SECTOR_KEY)


def refresh_sector_stats() -> dict:
    """Sektör medyanlarını yeniden hesapla + sakla. Yavaş (~evren boyu .info)."""
    stats = build_sector_stats(load_full_universe())
    get_kv().set(_SECTOR_KEY, stats, ttl_hours=48)
    sector_stats.clear()
    return stats


def score(ev: StockEvaluation) -> Score | None:
    """score_evaluation + kayıtlı sektör medyanları (varsa sektörel puanlama)."""
    return score_evaluation(ev, sector_stats())


# --- cache'li veri fonksiyonları (girdiye göre, süreli) ---------------

@st.cache_data(ttl=900, show_spinner=False)
def evaluate(symbols: tuple[str, ...]) -> list[StockEvaluation]:
    """Sembolleri değerlendir. 15 dk cache (aynı sembol seti tekrar sorulursa hızlı)."""
    return get_evaluator().evaluate_many(list(symbols))


@st.cache_data(ttl=3600, show_spinner=False)
def evaluate_universe(symbols: tuple[str, ...]) -> list[StockEvaluation]:
    """Tarama için tüm evreni değerlendir. 1 saat cache (ilk çalıştırma yavaş)."""
    return get_evaluator().evaluate_many(list(symbols))


@st.cache_data(ttl=900, show_spinner=False)
def known_names() -> dict[str, str]:
    return get_repo().known_names()


@st.cache_data(ttl=900, show_spinner=False)
def trending(bist_universe: tuple[str, ...], count: int = 12) -> TrendingReport:
    return build_trending_report(
        get_screener(), list(bist_universe), count=count, names=known_names(),
    )


@st.cache_data(ttl=1800, show_spinner=False)
def radar() -> RadarReport:
    return build_radar(
        get_screener(), get_evaluator(),
        load_bist_universe(), load_watchlist(),
        names=known_names(), sector_stats=sector_stats(),
    )


@st.cache_data(ttl=900, show_spinner=False)
def price_history(symbol: str, period: str = "2y"):
    return get_evaluator().provider.get_price_history(symbol, period)


_INDEX_SYMBOL = {"BIST": "XU100.IS", "US": "^GSPC"}


@st.cache_data(ttl=3600, show_spinner=False)
def index_history(market: str, period: str = "2y"):
    """Piyasa endeksi geçmişi (beta / relatif getiri için). market: 'BIST' | 'US'."""
    sym = _INDEX_SYMBOL.get(market, "^GSPC")
    try:
        return get_evaluator().provider.get_price_history(sym, period)
    except Exception:
        return None


@st.cache_data(ttl=1200, show_spinner=False)
def market_news(limit: int = 15) -> list[NewsItem]:
    return get_news().market_news(limit)


@st.cache_data(ttl=1200, show_spinner=False)
def ticker_news(symbol: str, limit: int = 8) -> list[NewsItem]:
    return get_news().ticker_news(symbol, limit)


@st.cache_resource
def get_statements() -> StatementsProvider:
    return StatementsProvider()


@st.cache_data(ttl=900, show_spinner=False)
def macro_metrics():
    from src.providers.macro import MacroProvider
    p = MacroProvider()
    return p.market_metrics(), p.tcmb_metrics()


@st.cache_data(ttl=3600, show_spinner=False)
def calendar_events(symbols: tuple[str, ...]):
    from src.providers.calendar import CalendarProvider
    return CalendarProvider().upcoming(list(symbols))


@st.cache_data(ttl=3600, show_spinner=False)
def financial_history(symbol: str, years: int = 4):
    return get_statements().get_history(symbol, years)


def eod_report(symbols: tuple[str, ...], date: str) -> tuple[EodReport, int]:
    """Gün sonu: değerlendir + kaydet + kıyasla. Cache YOK (kayıt yan etkisi var)."""
    evals = get_evaluator().evaluate_many(list(symbols))
    repo = get_repo()
    saved = repo.save_many(evals, date)
    return build_eod_report(evals, repo, date), saved


def take_snapshot(symbols: tuple[str, ...], date: str) -> int:
    """Sembolleri değerlendirip o günün snapshot'ı olarak kaydet. Kaç kayıt yazıldı."""
    evals = get_evaluator().evaluate_many(list(symbols))
    return get_repo().save_many(evals, date)


def snapshot_dates() -> list[tuple[str, int]]:
    """[(tarih, o gün kaydedilen sembol sayısı)] — yeni → eski."""
    repo = get_repo()
    return [(d, len(repo.symbols_on(d))) for d in repo.dates()]


def compare_snapshots(date_new: str, date_old: str) -> EodReport:
    return diff_stored(get_repo(), date_new, date_old)


# --- biçimlendirme ---------------------------------------------------

def fmt_num(v: float | None, digits: int = 2) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def fmt_trim(v: float | None, max_digits: int = 8, min_digits: int = 2) -> str:
    """Ondalığı max_digits'e kadar göster, sondaki sıfırları at, en az min_digits bırak."""
    if v is None:
        return "—"
    s = f"{v:.{max_digits}f}"
    if "." in s:
        s = s.rstrip("0")
    int_part, _, frac = s.partition(".")
    if len(frac) < min_digits:
        frac = frac.ljust(min_digits, "0")
    return f"{int_part}.{frac}" if frac else int_part


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%"


def fmt_pct_frac(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def fmt_count(v: float | None) -> str:
    if v is None:
        return "—"
    for div, suf in ((1e9, " Mr"), (1e6, " Mn"), (1e3, " B")):
        if abs(v) >= div:
            return f"{v / div:.1f}{suf}"
    return f"{v:.0f}"


def score_emoji(total: int) -> str:
    return "🟢" if total >= 70 else "🟡" if total >= 45 else "🔴"


def _news_card(box, it: NewsItem, with_image: bool) -> None:
    title = it.title.replace("[", "(").replace("]", ")")   # markdown link kırılmasın
    head = f"**[{title}]({it.url})**" if it.url else f"**{title}**"
    meta = it.source + (f" · {it.age_text}" if it.age_text else "")
    with box.container(border=True):
        if with_image and it.image_url:
            ic, tc = st.columns([1, 3])
            ic.image(it.image_url, use_container_width=True)
            tc.markdown(head)
            tc.caption(meta)
        else:
            st.markdown(head)
            st.caption(meta)


def render_news(
    items: list[NewsItem],
    empty_msg: str = "Haber bulunamadı.",
    *,
    columns: int = 1,
    with_images: bool = False,
) -> None:
    """Haberleri kart yapısında bas. columns>1 → grid; with_images → thumbnail."""
    if not items:
        st.caption(empty_msg)
        return
    cols = st.columns(columns) if columns > 1 else None
    for i, it in enumerate(items):
        _news_card(cols[i % columns] if cols else st, it, with_images)


def _alert_banner() -> None:
    """CLI --check-alerts'in yazdığı data/alerts.json varsa üstte göster."""
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "data" / "alerts.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    items = data.get("triggered", [])
    if items and data.get("checked_at", "")[:10] == datetime.now().strftime("%Y-%m-%d"):
        with st.container():
            st.warning("🔔 **" + str(len(items)) + " uyarı tetiklendi** — "
                       + " · ".join(f"{i['symbol']}: {i['message']}" for i in items[:4])
                       + ("  …" if len(items) > 4 else ""))


def page_header(title: str, icon: str = "📊", intro: str | None = None) -> None:
    st.set_page_config(page_title=f"{title} · Hisse Analiz", page_icon=icon, layout="wide")
    st.title(f"{icon} {title}")
    if intro:
        st.markdown(f"**{intro}**")
    st.caption(DISCLAIMER)
    _alert_banner()
