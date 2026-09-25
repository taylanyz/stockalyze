"""
Giriş noktası (entry point) — komut satırından çalışır.

Kullanım:
    python -m src.app AAPL                  # tek hisse, detaylı
    python -m src.app AAPL MSFT NVDA        # çoklu, karşılaştırma tablosu
    python -m src.app AAPL MSFT --detail    # çoklu ama her biri detaylı
    python -m src.app AAPL MSFT --save      # değerlendirmeyi DB'ye yaz
    python -m src.app --eod                 # gün sonu: watchlist'i değerlendir + kıyasla
    python -m src.app --history AAPL        # kayıtlı geçmişi göster

Bu katman SADECE sunumdan sorumlu: veriyi provider/analysis'ten alır,
ekrana basar. Hesaplama analysis katmanında.

UYARI: Bu araç yatırım tavsiyesi vermez. Ürettiği çıktılar yalnızca
araştırma amaçlıdır. Yatırım kararları için lisanslı bir uzmana danışın.
"""

from __future__ import annotations

import argparse
import sys

# Windows'ta çıktı bir dosyaya/pipe'a yönlendirilince stdout kod sayfası
# cp1254'e düşüyor ve tablo/ok karakterleri (▲, ─) çökertiyor.
# UTF-8'e sabitliyoruz.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.eod import EodReport, build_eod_report
from src.analysis.radar import RadarReport, build_radar
from src.analysis.scoring import Score
from src.analysis.scoring import score_evaluation as _score_eval

# Sektör medyanları — main() içinde bir kez yüklenir, sonra skorlamaya geçer.
_SECTOR_STATS: dict | None = None


def score_evaluation(ev):
    return _score_eval(ev, _SECTOR_STATS)
from src.analysis.trending import TrendingReport, build_trending_report
from src.config import (
    BIST_UNIVERSE_PATH,
    WATCHLIST_PATH,
    load_bist_universe,
    load_watchlist,
    read_symbol_file,
)
from src.evaluator import Evaluator
from src.glossary import TERMS
from src.models import (
    Fundamentals,
    Market,
    StockEvaluation,
    StockSnapshot,
    TechnicalIndicators,
)
from src.providers.factory import build_provider
from src.providers.screener import MarketScreener, Mover
from src.providers.yfinance_provider import YFinanceProvider
from src.storage.cache_provider import CachingProvider
from src.storage.database import Database
from src.storage.snapshot_repo import SnapshotRepository

console = Console()


# --- biçimlendirme yardımcıları -----------------------------------------

def format_money(value: float | None, currency: str | None) -> str:
    """Para değerini okunur biçime çevir; yoksa 'N/A'."""
    if value is None:
        return "N/A"
    suffix = f" {currency}" if currency else ""
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} Mr{suffix}"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f} Mn{suffix}"
    return f"{value:,.2f}{suffix}"


def format_pct(value: float | None) -> str:
    """Zaten yüzde olan bir değeri biçimlendir (ör. -2.51 -> '-2.51%')."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def format_ratio_as_pct(fraction: float | None) -> str:
    """Kesir olarak gelen oranı yüzdeye çevir (0.25 -> '25.0%')."""
    if fraction is None:
        return "N/A"
    return f"{fraction * 100:.1f}%"


def format_ratio(value: float | None, digits: int = 2) -> str:
    """Düz katsayı/oran (F/K, PD/DD, cari oran...)."""
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def short_name(name: str | None, limit: int = 22) -> str:
    if not name:
        return "—"
    return name if len(name) <= limit else name[: limit - 1] + "…"


def format_count(value: float | None) -> str:
    """Adet (hacim) — ondalıksız, K/Mn/Mr kısaltmalı."""
    if value is None:
        return "—"
    for div, suf in ((1e9, " Mr"), (1e6, " Mn"), (1e3, " B")):
        if abs(value) >= div:
            return f"{value / div:.1f}{suf}"
    return f"{value:.0f}"


# --- ekrana basma ------------------------------------------------------

def render_snapshot(snap: StockSnapshot) -> None:
    """Bir StockSnapshot'ı terminale tablo olarak bas."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()

    change_color = "green" if snap.is_up else "red" if (snap.day_change_pct or 0) < 0 else "white"

    table.add_row("Sembol", snap.symbol)
    table.add_row("Piyasa", snap.market.value)
    table.add_row("Borsa", snap.exchange or "N/A")
    table.add_row("Sektör", snap.sector or "N/A")
    table.add_row("Fiyat", format_money(snap.price, snap.currency))
    table.add_row("Önceki kapanış", format_money(snap.previous_close, snap.currency))
    table.add_row("Günlük değişim", f"[{change_color}]{format_pct(snap.day_change_pct)}[/]")
    table.add_row("Piyasa değeri", format_money(snap.market_cap, snap.currency))

    console.print(Panel(table, title=f"[bold]{snap.name}[/]", border_style="cyan"))


def render_fundamentals(fund: Fundamentals) -> None:
    """Temel analiz oranlarını tablo olarak bas."""
    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Oran", style="bold")
    table.add_column("Değer", justify="right")
    table.add_column("Ne anlama gelir", style="dim")

    table.add_row("F/K (12 ay)", format_ratio(fund.pe_trailing),
                  "Fiyat / hisse başı yıllık kâr")
    table.add_row("F/K (beklenti)", format_ratio(fund.pe_forward),
                  "Gelecek kâr tahminine göre F/K")
    table.add_row("PD/DD", format_ratio(fund.price_to_book),
                  "Piyasa değeri / defter (özkaynak) değeri")
    table.add_row("Net kâr marjı", format_ratio_as_pct(fund.profit_margin),
                  "Net kâr / satışlar")
    table.add_row("Faaliyet marjı", format_ratio_as_pct(fund.operating_margin),
                  "Faaliyet kârı / satışlar")
    table.add_row("ROE", format_ratio_as_pct(fund.return_on_equity),
                  "Net kâr / özkaynak (özkaynak kârlılığı)")
    table.add_row("Borç/Özkaynak", format_ratio(fund.debt_to_equity),
                  "Toplam borç / özkaynak (kaldıraç)")
    table.add_row("Cari oran", format_ratio(fund.current_ratio),
                  "Dönen varlık / kısa vadeli borç (likidite)")
    table.add_row("Temettü verimi", format_ratio_as_pct(fund.dividend_yield),
                  "Yıllık temettü / fiyat")

    console.print(Panel(table, title="[bold]Temel Analiz[/]", border_style="magenta"))


def render_technical(tech: TechnicalIndicators) -> None:
    """Teknik göstergeleri tablo olarak bas."""
    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Gösterge", style="bold")
    table.add_column("Değer", justify="right")
    table.add_column("Yorum", style="dim")

    # Trend rengi
    trend_color = {
        "Yükseliş": "green", "Düşüş": "red",
        "Yatay / Karışık": "yellow", "Belirsiz": "white",
    }.get(tech.trend.value, "white")

    table.add_row("Son kapanış", format_ratio(tech.last_close), tech.as_of)
    table.add_row("SMA 50", format_ratio(tech.sma_50),
                  f"fiyat {format_pct(tech.price_vs_sma50_pct)} uzakta")
    table.add_row("SMA 200", format_ratio(tech.sma_200),
                  f"fiyat {format_pct(tech.price_vs_sma200_pct)} uzakta")
    table.add_row("Trend", f"[{trend_color}]{tech.trend.value}[/]",
                  "fiyat / SMA50 / SMA200 dizilişi")

    if tech.trend_age_days:
        age_note = f"~{tech.trend_age_days} işlem günü"
        if tech.prior_trend is not None:
            age_note += f" · öncesinde {tech.prior_trend.value.lower()}"
        table.add_row("Trend yaşı", "taze" if tech.trend_age_days <= 10 else "", age_note)

    if tech.cross_signal:
        cross_color = "green" if "Altın" in tech.cross_signal else "red"
        table.add_row("Kesişim", f"[{cross_color}]{tech.cross_signal}[/]", "SMA50 × SMA200")
    else:
        table.add_row("Kesişim", "yok", f"son {60} günde kesişim yok")

    # RSI rengi: aşırı bölgeler dikkat çeksin
    rsi_color = {
        "Aşırı alım": "red", "Aşırı satım": "green",
        "Nötr": "white", "Belirsiz": "white",
    }.get(tech.rsi_zone.value, "white")
    table.add_row("RSI (14)", format_ratio(tech.rsi_14, 1),
                  f"[{rsi_color}]{tech.rsi_zone.value}[/]")

    vol_note = "N/A"
    if tech.volume_ratio is not None:
        vol_note = f"20g ortalamanın {tech.volume_ratio:.2f}x katı"
    table.add_row("Hacim (son gün)", format_count(tech.volume_last), vol_note)

    console.print(Panel(table, title="[bold]Teknik Analiz[/]", border_style="green"))


def _score_color(total: int) -> str:
    return "green" if total >= 70 else "yellow" if total >= 45 else "red"


def render_score(score: Score) -> None:
    """Puanı ve GEREKÇELERİNİ bas (kara kutu değil)."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(justify="right")
    table.add_column()
    for r in score.reasons:
        sign_color = "green" if r.points > 0 else "red"
        table.add_row(
            f"[{sign_color}]{r.points:+d}[/]",
            f"{r.label}  [dim]({r.category})[/dim]",
        )
    if not score.reasons:
        table.add_row("", "[dim]Puanlanacak yeterli veri yok[/dim]")

    color = _score_color(score.total)
    title = (
        f"[bold][{color}]{score.total}/100[/] · {score.verdict}[/] "
        f"[dim](temel {score.fundamental:+d} · teknik {score.technical:+d} · taban 50)[/dim]"
    )
    console.print(Panel(table, title=title, title_align="left", border_style=color))


def _fmt_big(v: float | None) -> str:
    if v is None:
        return "—"
    for div, s in ((1e9, "Mr"), (1e6, "Mn"), (1e3, "B")):
        if abs(v) >= div:
            return f"{v / div:,.1f} {s}"
    return f"{v:,.0f}"


def render_statements(symbol: str) -> None:
    """Bilanço Karnesi — çok dönemli mali tablo + trend özeti."""
    from src.analysis.statements import summarize
    from src.providers.statements import StatementsProvider

    try:
        h = StatementsProvider().get_history(symbol)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[dim]Bilanço Karnesi alınamadı: {exc}[/dim]")
        return

    c = h.currency or "?"
    table = Table(title="Bilanço Karnesi", title_justify="left",
                  box=box.SIMPLE_HEAD, header_style="bold", pad_edge=False)
    table.add_column("Kalem", style="bold", no_wrap=True)
    for p in h.periods:
        table.add_column(p.label, justify="right", no_wrap=True)

    def row(name, fn):
        table.add_row(name, *[fn(p) for p in h.periods])

    row(f"Satış ({c})", lambda p: _fmt_big(p.revenue))
    row(f"Net kâr ({c})", lambda p: _fmt_big(p.net_income))
    row("Net marj", lambda p: format_ratio_as_pct(p.net_margin))
    row("Faaliyet marjı", lambda p: format_ratio_as_pct(p.operating_margin))
    row(f"Özkaynak ({c})", lambda p: _fmt_big(p.equity))
    row("Borç/Özkaynak", lambda p: format_ratio(p.debt_to_equity))
    row(f"Faaliyet nakit akışı ({c})", lambda p: _fmt_big(p.operating_cash_flow))

    console.print(table)
    console.print(f"[dim]Kaynak: {h.source}. Ara dönem (X ay) kümülatiftir.[/dim]")
    _TAG_STYLE = {"olumlu": "green", "temkinli": "yellow", "riskli": "red", "notr": "dim"}
    for text, tag in summarize(h):
        style = _TAG_STYLE.get(tag, "")
        console.print(f"  • [{style}]{text}[/{style}]" if style else f"  • {text}")


def render_risk(symbol: str, market: Market, provider) -> None:
    from src.analysis.risk import compute_risk, describe_risk

    idx_sym = "XU100.IS" if market is Market.BIST else "^GSPC"
    try:
        ph = provider.get_price_history(symbol)
        ih = provider.get_price_history(idx_sym)
    except Exception:
        return
    r = compute_risk(ph, ih)
    lines = describe_risk(r)
    if lines:
        console.print("[bold]Risk[/]")
        for line in lines:
            console.print(f"  • {line}")


def render_detail(ev: StockEvaluation, provider=None) -> None:
    """Tek bir değerlendirmeyi tüm panelleriyle bas."""
    if not ev.ok:
        console.print(f"[red]{ev.symbol}:[/] {ev.error}")
        return
    render_snapshot(ev.snapshot)
    if ev.fundamentals is not None:
        render_fundamentals(ev.fundamentals)
    render_statements(ev.snapshot.symbol)
    if ev.technical is not None:
        render_technical(ev.technical)
    if provider is not None:
        render_risk(ev.snapshot.symbol, ev.snapshot.market, provider)
    score = score_evaluation(ev)
    if score is not None:
        render_score(score)


# Karşılaştırma tablosunda trendi kısa sembolle gösteririz (yer kazanır).
_TREND_GLYPH = {
    "Yükseliş": ("[green]▲[/]"),
    "Düşüş": ("[red]▼[/]"),
    "Yatay / Karışık": ("[yellow]~[/]"),
    "Belirsiz": ("[dim]?[/]"),
}


def _comparison_table(title: str, rows: list[StockEvaluation]) -> Table:
    """Bir piyasa grubu için kompakt karşılaştırma tablosu kur."""
    table = Table(
        title=title, title_justify="left", header_style="bold",
        box=box.SIMPLE_HEAD, pad_edge=False, padding=(0, 1),
    )
    table.add_column("Sembol", style="bold", no_wrap=True)
    table.add_column("Şirket", style="dim", no_wrap=True, max_width=20, overflow="ellipsis")
    table.add_column("Skor", justify="right", no_wrap=True)
    table.add_column("Fiyat", justify="right", no_wrap=True)
    table.add_column("Gün %", justify="right", no_wrap=True)
    table.add_column("F/K", justify="right", no_wrap=True)
    table.add_column("PD/DD", justify="right", no_wrap=True)
    table.add_column("ROE", justify="right", no_wrap=True)
    table.add_column("T", justify="center", no_wrap=True)   # trend sembolü
    table.add_column("RSI", justify="right", no_wrap=True)
    table.add_column("Hac×", justify="right", no_wrap=True)

    # En yüksek skordan düşüğe sırala (elemede işe yarasın).
    scored = [(ev, score_evaluation(ev)) for ev in rows]
    scored.sort(key=lambda t: t[1].total if t[1] else -1, reverse=True)

    for ev, score in scored:
        snap, fund, tech = ev.snapshot, ev.fundamentals, ev.technical

        change = snap.day_change_pct if snap else None
        change_color = "green" if (change or 0) > 0 else "red" if (change or 0) < 0 else "white"

        score_txt = "N/A"
        if score is not None:
            score_txt = f"[{_score_color(score.total)}]{score.total}[/]"

        trend_glyph = _TREND_GLYPH.get(tech.trend.value, "[dim]?[/]") if tech else "[dim]?[/]"

        rsi_txt, rsi_color = "N/A", "white"
        if tech is not None and tech.rsi_14 is not None:
            rsi_txt = f"{tech.rsi_14:.0f}"
            rsi_color = {
                "Aşırı alım": "red", "Aşırı satım": "green",
            }.get(tech.rsi_zone.value, "white")

        vol_txt = f"{tech.volume_ratio:.2f}" if tech and tech.volume_ratio else "N/A"

        table.add_row(
            ev.symbol,
            short_name(snap.name if snap else None),
            score_txt,
            format_ratio(snap.price if snap else None),
            f"[{change_color}]{format_pct(change)}[/]",
            format_ratio(fund.pe_trailing if fund else None),
            format_ratio(fund.price_to_book if fund else None),
            format_ratio_as_pct(fund.return_on_equity if fund else None),
            trend_glyph,
            f"[{rsi_color}]{rsi_txt}[/]",
            vol_txt,
        )
    return table


def render_comparison(evaluations: list[StockEvaluation]) -> None:
    """
    Çoklu değerlendirmeyi piyasaya göre GRUPLAYARAK bas.
    BIST ve ABD ayrı tablolar (kullanıcı isteği: ayrı değerlendirme).
    """
    ok = [e for e in evaluations if e.ok]
    failed = [e for e in evaluations if not e.ok]

    groups: list[tuple[str, list[StockEvaluation]]] = [
        ("BIST", [e for e in ok if e.snapshot.market is Market.BIST]),
        ("ABD (NYSE / NASDAQ)", [e for e in ok if e.snapshot.market is Market.US]),
    ]
    any_shown = False
    for title, rows in groups:
        if rows:
            cur = rows[0].snapshot.currency or ""
            console.print(_comparison_table(f"{title}  ·  {cur}".strip(" ·"), rows))
            any_shown = True
    if any_shown:
        console.print(
            "[dim]T: ▲ yükseliş  ▼ düşüş  ~ yatay  ?  belirsiz   ·   "
            "Hac×: son gün hacmi / 20g ortalama[/dim]"
        )
        console.print()

    if failed:
        console.print("[red]Değerlendirilemeyen semboller:[/]")
        for e in failed:
            console.print(f"  [red]{e.symbol}[/] — {e.error}")


def render_history(rows: list[dict], symbol: str) -> None:
    """Bir sembolün kayıtlı geçmişini tablo olarak bas."""
    if not rows:
        console.print(f"[yellow]{symbol} için kayıtlı snapshot yok.[/] (`--save` ile biriktir)")
        return
    table = Table(title=f"{symbol} — kayıtlı geçmiş", title_justify="left",
                  box=box.SIMPLE_HEAD, header_style="bold")
    table.add_column("Tarih", no_wrap=True)
    table.add_column("Fiyat", justify="right")
    table.add_column("Gün %", justify="right")
    table.add_column("F/K", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("Trend")
    for r in rows:
        table.add_row(
            r["snapshot_date"],
            format_ratio(r["price"]),
            format_pct(r["day_change_pct"]),
            format_ratio(r["pe_trailing"]),
            format_ratio(r["rsi_14"], 0),
            r["trend"] or "N/A",
        )
    console.print(table)


def render_glossary() -> None:
    """Terim sözlüğünü bas."""
    console.print(Panel.fit(
        "[bold]Terim Sözlüğü[/] — bu göstergeler ne anlama geliyor?",
        border_style="cyan",
    ))
    for t in TERMS:
        console.print(f"\n[bold cyan]{t.key}[/]  [dim]— {t.name}[/]")
        console.print(f"  [white]Nedir:[/] {t.what}")
        console.print(f"  [white]Yorum:[/] [dim]{t.reading}[/]")
    console.print(
        "\n[dim]Bu açıklamalar genel bilgi amaçlıdır, yatırım tavsiyesi değildir.[/dim]"
    )


def _mover_table(title: str, movers: list[Mover]) -> Table:
    table = Table(title=title, title_justify="left", box=box.SIMPLE_HEAD,
                  header_style="bold", pad_edge=False)
    table.add_column("Sembol", style="bold", no_wrap=True)
    table.add_column("Şirket", style="dim", no_wrap=True, max_width=20, overflow="ellipsis")
    table.add_column("Fiyat", justify="right", no_wrap=True)
    table.add_column("Gün %", justify="right", no_wrap=True)
    table.add_column("Hacim", justify="right", no_wrap=True)
    table.add_column("Skor", justify="right", no_wrap=True)
    for m in movers:
        chg = m.day_change_pct
        c = "green" if (chg or 0) > 0 else "red" if (chg or 0) < 0 else "white"
        score_txt = "—"
        if m.score is not None:
            score_txt = f"[{_score_color(m.score)}]{m.score}[/]"
        table.add_row(
            m.symbol,
            short_name(m.name),
            format_ratio(m.price),
            f"[{c}]{format_pct(chg)}[/]",
            format_count(m.volume),
            score_txt,
        )
    return table


_TAG_COLOR = {"olumlu": "green", "temkinli": "yellow", "riskli": "red", "notr": "white"}


_TAG_LABEL = {"olumlu": "olumlu", "temkinli": "temkinli", "riskli": "riskli", "notr": "nötr"}


def _radar_section(title: str, rows: list, note_header: str) -> None:
    table = Table(title=title, title_justify="left", box=box.SIMPLE_HEAD,
                  header_style="bold", pad_edge=False)
    table.add_column("Sembol", style="bold", no_wrap=True)
    table.add_column("Şirket", style="dim", no_wrap=True, max_width=20, overflow="ellipsis")
    table.add_column("Skor", justify="right", no_wrap=True)
    table.add_column("İlgi", justify="right", no_wrap=True)
    table.add_column("Gün %", justify="right", no_wrap=True)
    table.add_column("5g %", justify="right", no_wrap=True)
    table.add_column("Trend", no_wrap=True)
    table.add_column("RSI", justify="right", no_wrap=True)
    table.add_column("Durum", no_wrap=True)
    for r in rows:
        tcol = {"Yükseliş": "green", "Düşüş": "red"}.get(r.trend.value, "yellow")
        score_txt = "—" if r.score is None else f"[{_score_color(r.score)}]{r.score}[/]"
        table.add_row(
            r.symbol, short_name(r.name), score_txt, str(r.attention),
            format_pct(r.day_change_pct), format_pct(r.ret_5d_pct),
            f"[{tcol}]{r.trend.value}[/]", format_ratio(r.rsi_14, 0),
            f"[{_TAG_COLOR.get(r.tag, 'white')}]{_TAG_LABEL.get(r.tag, r.tag)}[/]",
        )
    console.print(table)
    console.print(f"[dim]{note_header}:[/dim]")
    for r in rows:
        c = _TAG_COLOR.get(r.tag, "white")
        console.print(f"  [{c}]{r.symbol}[/] — {r.note}")
        for line in r.trend_reason:
            console.print(f"      [dim]• {line}[/dim]")
    console.print()


_RADAR_GOOD = 60   # bu skorun üstü "skoru iyi"


def render_radar(report: RadarReport) -> None:
    console.rule("[bold]Radar — Skoru İyi + İlgi Gören + Trend Yorumlu[/]")

    for market, label in ((Market.BIST, "BIST"), (Market.US, "ABD (NYSE / NASDAQ)")):
        rows = [r for r in report.hot if r.market is market]
        good = [r for r in rows if (r.score or 0) >= _RADAR_GOOD]
        weak = [r for r in rows if (r.score or 0) < _RADAR_GOOD]
        if good:
            _radar_section(f"{label} — skoru iyi + ilgi gören",
                           good, "Konumlanma (almayı düşünen bakışı)")
        if weak:
            _radar_section(f"{label} — sadece ilgi gören (skor < {_RADAR_GOOD})",
                           weak, "Konumlanma (almayı düşünen bakışı)")

    if report.watchlist:
        _radar_section("Watchlist durumu",
                       report.watchlist, "Konumlanma (elde tutan bakışı)")
    console.print(
        "[yellow]Konumlanma notları göstergelerin ne söylediğini tarif eder — "
        "al/sat talimatı DEĞİLDİR.[/yellow]\n"
        "[dim]İlgi = hacim artışı + günlük/haftalık hareket (0-100). "
        "Bu çıktı yatırım tavsiyesi değildir.[/dim]"
    )


def render_trending(report: TrendingReport, scored: bool) -> None:
    console.rule("[bold]Ana Sayfa — Piyasada Ne Hareketleniyor[/]")
    labels = {"gainers": "En çok yükselenler", "losers": "En çok düşenler",
              "actives": "En çok işlem görenler"}

    console.print("[bold cyan]ABD (NYSE / NASDAQ)[/]")
    for k in ("gainers", "losers", "actives"):
        rows = report.us.get(k) or []
        if rows:
            console.print(_mover_table(labels[k], rows))
    console.print("\n[bold cyan]BIST (bist30.txt evreni)[/]")
    for k in ("gainers", "losers", "actives"):
        rows = report.bist.get(k) or []
        if rows:
            console.print(_mover_table(labels[k], rows))

    if not scored:
        console.print("[dim]Skor sütunu için: --trending --deep (ilk sıralar puanlanır, yavaş).[/dim]")
    console.print(
        "[dim]Bu çıktı yatırım tavsiyesi değildir; yalnızca araştırma amaçlıdır.[/dim]"
    )


def _eod_table(title: str, changes: list) -> Table:
    table = Table(title=title, title_justify="left", box=box.SIMPLE_HEAD,
                  header_style="bold")
    table.add_column("Sembol", style="bold", no_wrap=True)
    table.add_column("Şirket", style="dim", no_wrap=True, max_width=20, overflow="ellipsis")
    table.add_column("Fiyat", justify="right", no_wrap=True)
    table.add_column("Gün %", justify="right", no_wrap=True)
    table.add_column("Skor", justify="right", no_wrap=True)
    table.add_column("Δ Skor", justify="right", no_wrap=True)
    table.add_column("Yeni sinyaller")
    for c in changes:
        chg_color = "green" if (c.day_change_pct or 0) > 0 else "red" if (c.day_change_pct or 0) < 0 else "white"
        delta_txt = "—"
        if c.score_delta is not None:
            dc = "green" if c.score_delta > 0 else "red" if c.score_delta < 0 else "dim"
            delta_txt = f"[{dc}]{c.score_delta:+d}[/]"
        table.add_row(
            c.symbol,
            short_name(c.name),
            format_ratio(c.price),
            f"[{chg_color}]{format_pct(c.day_change_pct)}[/]",
            f"[{_score_color(c.score_now)}]{c.score_now}[/]",
            delta_txt,
            "  ·  ".join(c.new_signals) if c.new_signals else "[dim]—[/dim]",
        )
    return table


def render_eod(report: EodReport) -> None:
    """Gün sonu raporunu bas."""
    console.rule(f"[bold]Gün Sonu Değerlendirmesi — {report.date}[/]")

    groups = [
        ("BIST", [c for c in report.changes if c.market is Market.BIST]),
        ("ABD (NYSE / NASDAQ)", [c for c in report.changes if c.market is Market.US]),
    ]
    for title, changes in groups:
        if changes:
            console.print(_eod_table(title, changes))
            console.print()

    highlights = report.with_signals
    if highlights:
        console.print("[bold]Öne çıkanlar (yeni sinyal olanlar):[/]")
        for c in highlights:
            console.print(f"  [bold]{c.symbol}[/] — " + "; ".join(c.new_signals))
    else:
        console.print("[dim]Bugün kayda değer yeni teknik sinyal yok.[/dim]")

    if report.failed:
        console.print("\n[red]Değerlendirilemeyenler:[/]")
        for sym, err in report.failed:
            console.print(f"  [red]{sym}[/] — {err}")

    if any(c.score_prev is None for c in report.changes):
        console.print(
            "\n[dim]Not: bazı hisselerde önceki kayıt yok — Δ Skor ilk günden sonra anlamlı.[/dim]"
        )


def _run_eod(args, db: Database) -> int:
    """--eod akışı: değerlendir -> kaydet -> önceki kayıtla kıyasla -> raporla."""
    from datetime import datetime

    symbols = args.symbols or load_watchlist()
    if not symbols:
        console.print(
            f"[red]Watchlist boş.[/] {WATCHLIST_PATH} dosyasına sembol ekle "
            "veya sembolleri argüman olarak ver."
        )
        return 1

    evaluator = Evaluator(build_provider(None if args.no_cache else db))
    with console.status(f"{len(symbols)} sembol değerlendiriliyor..."):
        evaluations = evaluator.evaluate_many(symbols)

    repo = SnapshotRepository(db)
    today = datetime.now().strftime("%Y-%m-%d")

    # ÖNCE bugünün snapshot'ını kaydet, SONRA kıyasla:
    # build_eod_report yalnızca `today`den küçük tarihlere bakar,
    # bu yüzden bugünü kaydetmek kıyası bozmaz.
    saved = repo.save_many(evaluations, today)

    report = build_eod_report(evaluations, repo, today)
    render_eod(report)
    console.print(f"\n[dim]{saved} kayıt güncellendi ({today}).[/dim]")
    console.print(
        "[dim]Bu çıktı yatırım tavsiyesi değildir; yalnızca araştırma amaçlıdır.[/dim]"
    )
    return 0 if any(e.ok for e in evaluations) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hisse senedi değerlendirme aracı (temel + teknik özet)."
    )
    parser.add_argument(
        "symbols", nargs="*",
        help="Bir veya daha fazla sembol, örn. AAPL MSFT THYAO.IS",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Çoklu sembolde bile her hisseyi ayrı ayrı detaylı göster.",
    )
    parser.add_argument(
        "--no-fundamentals", action="store_true", help="Temel analizi atla."
    )
    parser.add_argument(
        "--no-technical", action="store_true", help="Teknik analizi atla."
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Değerlendirmeyi bugünün tarihiyle veritabanına kaydet.",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Fiyat geçmişi önbelleğini kullanma (her zaman taze çek).",
    )
    parser.add_argument(
        "--history", metavar="SEMBOL",
        help="Ağa çıkmadan, bu sembolün kayıtlı geçmişini göster ve çık.",
    )
    parser.add_argument(
        "--eod", action="store_true",
        help="Gün sonu: sembolleri (yoksa watchlist) değerlendir, kaydet, "
             "önceki kayıtla kıyasla.",
    )
    parser.add_argument(
        "--trending", action="store_true",
        help="Ana sayfa: ABD + BIST trend listeleri (watchlist'ten bağımsız).",
    )
    parser.add_argument(
        "--radar", action="store_true",
        help="Skoru iyi + ilgi gören hisseler + trend/konumlanma notu (yavaş).",
    )
    parser.add_argument(
        "--deep", action="store_true",
        help="--trending ile: listelerin ilk sıralarını puanla (yavaş).",
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Önbelleği temizle ve çık."
    )
    parser.add_argument(
        "--terimler", action="store_true",
        help="F/K, PD/DD, RSI gibi terimlerin açıklamasını göster ve çık.",
    )
    parser.add_argument(
        "--haberler", action="store_true",
        help="Türkçe finans kaynaklarından son piyasa haberlerini göster ve çık.",
    )
    parser.add_argument(
        "--refresh-sectors", action="store_true",
        help="Sektör medyanlarını yeniden hesapla (yavaş, ~evren boyu) ve çık.",
    )
    parser.add_argument(
        "--check-alerts", action="store_true",
        help="Aktif uyarı kurallarını kontrol et; tetiklenenleri data/alerts.json'a yaz.",
    )
    parser.add_argument(
        "--db", metavar="YOL", default=None,
        help="Veritabanı dosyası yolu (varsayılan: data/hisse.db).",
    )
    args = parser.parse_args(argv)

    if args.terimler:
        render_glossary()
        return 0

    if args.check_alerts:
        import json
        from datetime import datetime, timezone
        from src.analysis.alerts import check_alerts
        from src.analysis.sector import _KEY as _SK
        from src.storage.alerts_repo import AlertsRepository
        from src.storage.kv_store import KVStore

        db = Database(args.db)
        arepo = AlertsRepository(db)
        rules = arepo.all(active_only=True)
        triggered_out: list[dict] = []
        if rules:
            evaluator = Evaluator(build_provider(db))
            syms = sorted({r.symbol for r in rules})
            with console.status(f"{len(syms)} sembol için {len(rules)} kural kontrol ediliyor..."):
                evals = {e.symbol: e for e in evaluator.evaluate_many(syms)}
            ss = KVStore(db).get(_SK)
            for t in check_alerts(rules, evals, ss):
                triggered_out.append({"symbol": t.symbol, "message": t.message})
                arepo.mark_fired(t.rule_id)
        out = {"checked_at": datetime.now(timezone.utc).isoformat(), "triggered": triggered_out}
        path = Database().path.parent / "alerts.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        db.close()
        if triggered_out:
            console.print(f"[yellow]{len(triggered_out)} uyarı tetiklendi:[/]")
            for t in triggered_out:
                console.print(f"  🔔 {t['symbol']} — {t['message']}")
        else:
            console.print("[dim]Tetiklenen uyarı yok.[/dim]")
        return 0

    if args.refresh_sectors:
        from src.analysis.sector import _KEY as _SK
        from src.analysis.sector import build_sector_stats
        from src.config import load_full_universe
        from src.storage.kv_store import KVStore

        db = Database(args.db)
        syms = load_full_universe()
        with console.status(f"{len(syms)} sembol için sektör medyanları hesaplanıyor..."):
            stats = build_sector_stats(syms)
        KVStore(db).set(_SK, stats, ttl_hours=48)
        db.close()
        secs = stats.get("sectors", {})
        console.print(f"[green]{len(secs)} sektör medyanı kaydedildi.[/]")
        for name, d in sorted(secs.items()):
            console.print(f"  {name}: F/K medyan {d.get('pe_median')} · "
                          f"PD/DD medyan {d.get('pb_median')} ({d['count']} hisse)")
        return 0

    if args.haberler:
        from src.providers.news import NewsProvider

        console.rule("[bold]Piyasa Haberleri[/]")
        items = NewsProvider().market_news(20)
        if not items:
            console.print("[yellow]Haber alınamadı (kaynaklara ulaşılamadı).[/]")
        for it in items:
            meta = f"[dim]{it.source}" + (f" · {it.age_text}" if it.age_text else "") + "[/dim]"
            console.print(f"• {it.title}\n  {meta}\n  [blue]{it.url}[/blue]")
        console.print("\n[dim]Sadece bilgilendirme — yatırım tavsiyesi değildir.[/dim]")
        return 0

    # Veritabanı, kalıcı özelliklerden biri istendiğinde açılır.
    needs_db = (args.save or args.history or args.eod or args.clear_cache
                or args.trending or args.radar or not args.no_cache)
    db = Database(args.db) if (args.db or needs_db) else None

    global _SECTOR_STATS
    if db is not None:
        from src.storage.kv_store import KVStore
        from src.analysis.sector import _KEY as _SK
        _SECTOR_STATS = KVStore(db).get(_SK)

    try:
        if args.clear_cache:
            CachingProvider(YFinanceProvider(), db).clear_cache()
            console.print("[green]Önbellek temizlendi.[/]")
            return 0

        # --history: sadece okuma, ağ yok.
        if args.history:
            repo = SnapshotRepository(db)
            render_history(repo.history(args.history), args.history.upper())
            return 0

        # --trending: ana sayfa trend listeleri.
        if args.trending:
            evaluator = Evaluator(build_provider(None if args.no_cache else db)) if args.deep else None
            names = SnapshotRepository(db).known_names() if db else {}
            with console.status("Piyasa taranıyor..."):
                report = build_trending_report(
                    MarketScreener(),
                    read_symbol_file(BIST_UNIVERSE_PATH),
                    evaluator=evaluator,
                    score_top=3 if args.deep else 0,
                    names=names,
                )
            render_trending(report, scored=args.deep)
            return 0

        # --radar: skoru iyi + ilgi gören + trend yorumlu.
        if args.radar:
            evaluator = Evaluator(build_provider(None if args.no_cache else db))
            names = SnapshotRepository(db).known_names() if db else {}
            with console.status("Radar taranıyor (bulk indirme + değerlendirme)..."):
                report = build_radar(
                    MarketScreener(), evaluator,
                    load_bist_universe(), load_watchlist(), names=names,
                    sector_stats=_SECTOR_STATS,
                )
            render_radar(report)
            return 0

        # --eod: watchlist veya verilen semboller, kaydet + kıyasla.
        if args.eod:
            return _run_eod(args, db)

        if not args.symbols:
            parser.error("en az bir sembol gerekli (veya --history / --eod kullan).")

        evaluator = Evaluator(build_provider(None if args.no_cache else db))

        with console.status("Veri çekiliyor..."):
            evaluations = evaluator.evaluate_many(
                args.symbols,
                with_fundamentals=not args.no_fundamentals,
                with_technical=not args.no_technical,
            )

        single = len(evaluations) == 1
        if single or args.detail:
            for i, ev in enumerate(evaluations):
                if i:
                    console.print()
                render_detail(ev, evaluator.provider)
        else:
            render_comparison(evaluations)

        if args.save:
            saved = SnapshotRepository(db).save_many(evaluations)
            console.print(f"[green]{saved} kayıt veritabanına yazıldı.[/]")

        console.print(
            "[dim]Bu çıktı yatırım tavsiyesi değildir; yalnızca araştırma amaçlıdır. "
            "Terimler için: python -m src.app --terimler[/dim]"
        )
        return 0 if any(e.ok for e in evaluations) else 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
