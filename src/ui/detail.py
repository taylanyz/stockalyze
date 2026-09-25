"""
Tek hisse detay paneli — hem 'Hisse Detay' sayfası hem Radar'ın yan paneli
aynı fonksiyonu kullanır (kod tekrarı olmasın).
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.analysis.risk import RiskMetrics, compute_risk, describe_risk
from src.analysis.snowflake import AXES, Snowflake, compute_snowflake
from src.analysis.statements import summarize
from src.analysis.technical import describe_trend
from src.glossary import TERMS_BY_KEY
from src.providers.base import ProviderError
from src.ui.chart import price_line_chart, rsi_chart, volume_chart
from src.ui.common import (
    evaluate,
    financial_history,
    fmt_num,
    fmt_pct,
    fmt_pct_frac,
    index_history,
    price_history,
    render_news,
    score_emoji,
    ticker_news,
)
from src.ui.common import score as score_evaluation
from src.ui.explain import (
    TAG_ICON,
    badge_cross,
    badge_current_ratio,
    badge_debt_equity,
    badge_dividend,
    badge_health,
    badge_margin,
    badge_pb,
    badge_pe,
    badge_roe,
    badge_rsi,
    badge_trend_persistence,
    badge_volatility,
    badge_volume,
)


def _terms_expander(keys: list[str]) -> None:
    with st.expander("📖 Bu bölümdeki terimler ne demek?"):
        for k in keys:
            t = TERMS_BY_KEY.get(k)
            if t is None:
                continue
            st.markdown(f"**{t.name}** — {t.what}  \n*Nasıl okunur:* {t.reading}")


def _metric_grid(
    items: list[tuple[str, str, tuple[str, str] | None]], cols: int = 3,
) -> None:
    """(etiket, değer, (emoji, durum_metni)|None) üçlülerini kart ızgarası olarak göster."""
    for start in range(0, len(items), cols):
        row = items[start:start + cols]
        cs = st.columns(cols)
        for c, (label, value, badge) in zip(cs, row):
            with c.container(border=True):
                st.caption(label)
                st.markdown(f"**{value}**")
                if badge:
                    st.markdown(f"{badge[0]} {badge[1]}")


def _big(v: float | None, cur: str | None = None) -> str:
    if v is None:
        return "—"
    suf = f" {cur}" if cur else ""
    for div, s in ((1e9, " Mr"), (1e6, " Mn"), (1e3, " B")):
        if abs(v) >= div:
            return f"{v / div:,.1f}{s}{suf}"
    return f"{v:,.0f}{suf}"


def _render_snowflake(ev) -> Snowflake | None:
    try:
        hist = financial_history(ev.symbol)
    except Exception:
        hist = None
    sf = compute_snowflake(ev, hist)
    vals = [sf.values.get(a) or 0 for a in AXES]
    if not any(vals):
        st.caption("Profil için yeterli temel veri yok.")
        return sf
    fig = go.Figure(go.Scatterpolar(
        r=vals + [vals[0]], theta=AXES + [AXES[0]],
        fill="toself", line_color="#4c8bf5", name="",
    ))
    fig.update_layout(
        title=dict(text="Değer · Kârlılık · Sağlık · Büyüme · Temettü", font=dict(size=11)),
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)),
        showlegend=False, height=280, margin=dict(l=30, r=30, t=34, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(" · ".join(
        f"{a} {int(sf.values[a])}" for a in AXES if sf.values.get(a) is not None
    ))
    return sf


def _render_risk(hist_df, market: str) -> RiskMetrics | None:
    if hist_df is None:
        st.caption("Risk için fiyat geçmişi yok.")
        return None
    idx = index_history(market)
    r = compute_risk(hist_df, idx)
    for line in describe_risk(r):
        st.markdown(f"- {line}")
    return r


def _render_statements(symbol: str) -> None:
    st.markdown("**📊 Bilanço Karnesi**")
    try:
        h = financial_history(symbol)
    except ProviderError as e:
        st.caption(f"Mali tablo geçmişi alınamadı: {e}")
        return
    except Exception as e:  # noqa: BLE001
        st.caption(f"Mali tablo geçmişi alınamadı: {e}")
        return

    c = h.currency or "?"
    rows = {
        "Kalem": [f"Satış ({c})", f"Brüt kâr ({c})", f"Faaliyet kârı ({c})",
                  f"FAVÖK ({c})", f"Net kâr ({c})", "—",
                  "Brüt marj", "Faaliyet marjı", "Net marj", "—",
                  f"Özkaynak ({c})", f"Toplam borç ({c})", "Borç/Özkaynak",
                  "Cari oran", f"Faaliyet nakit akışı ({c})"],
    }
    for p in h.periods:
        rows[p.label] = [
            _big(p.revenue), _big(p.gross_profit), _big(p.operating_profit),
            _big(p.ebitda), _big(p.net_income), "",
            fmt_pct_frac(p.gross_margin), fmt_pct_frac(p.operating_margin),
            fmt_pct_frac(p.net_margin), "",
            _big(p.equity), _big(p.total_debt), fmt_num(p.debt_to_equity),
            fmt_num(p.current_ratio), _big(p.operating_cash_flow),
        ]
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(f"Kaynak: {h.source}. "
               "Ara dönem (X ay) sütunu kümülatiftir — yıllıkla birebir kıyaslanmaz.")

    for text, tag in summarize(h):
        st.markdown(f"- {TAG_ICON.get(tag, '')} {text}")

CHART_CAPTION = (
    "**Fiyat:** günlük kapanış (temettü/bölünme etkisinden arındırılmış).  \n"
    "**SMA 50:** son 50 günün kapanış ortalaması — kısa/orta vadeli yön.  \n"
    "**SMA 200:** son 200 günün ortalaması — uzun vadeli yön. "
    "Fiyat > SMA50 > SMA200 ‘yükseliş dizilişi’; SMA50'nin SMA200'ü yukarı "
    "kesmesi *altın kesişim* (boğa), aşağı kesmesi *ölüm kesişimi*."
)


def render_detail_panel(symbol: str, *, compact: bool = False) -> None:
    """symbol için tam detay: metrikler + grafik + temel/teknik + puan kırılımı."""
    symbol = symbol.strip().upper()
    with st.spinner(f"{symbol} değerlendiriliyor..."):
        ev = evaluate((symbol,))[0]

    if not ev.ok:
        st.error(f"{symbol}: {ev.error}")
        return

    snap = ev.snapshot
    score = score_evaluation(ev)

    st.markdown(f"### {snap.name} · {snap.symbol}")
    cols = st.columns(2 if compact else 4)
    cols[0].metric("Fiyat", f"{fmt_num(snap.price)} {snap.currency or ''}",
                   fmt_pct(snap.day_change_pct))
    cols[1].metric("Piyasa", snap.market.value)
    if not compact:
        cols[2].metric("Sektör", snap.sector or "—")
    (cols[1] if compact else cols[3]).metric(
        f"Puan {score_emoji(score.total)}" if score else "Puan",
        f"{score.total}/100" if score else "—",
        score.verdict if score else None,
    )

    # --- grafik (fiyat + hareketli ortalamalar, altında hacim + RSI yan yana) ---
    st.markdown("**Fiyat grafiği — hareketli ortalamalar · hacim · RSI**")

    _RANGES = {"1A": 30, "3A": 90, "6A": 180, "1Y": 365, "2Y": 730, "5Y": 1825}
    rc1, rc2 = st.columns([2, 3])
    with rc1:
        try:
            pick = st.segmented_control(
                "Aralık", list(_RANGES), default="1Y", key=f"rng_{snap.symbol}",
                label_visibility="collapsed",
            )
        except Exception:  # eski Streamlit
            pick = st.radio("Aralık", list(_RANGES), index=3, horizontal=True,
                            key=f"rng_{snap.symbol}", label_visibility="collapsed")
    view_days = _RANGES.get(pick or "1Y", 365)

    hist_df = None
    _chart_config = {"displayModeBar": False, "scrollZoom": False}
    try:
        hist_df = price_history(symbol, "5y")   # göstergeler tam geçmişten
        st.plotly_chart(
            price_line_chart(hist_df, f"{snap.symbol} — Fiyat", view_days),
            use_container_width=True, config=_chart_config,
        )
        vcol, rcol = st.columns(2)
        vcol.plotly_chart(volume_chart(hist_df, view_days),
                          use_container_width=True, config=_chart_config)
        rcol.plotly_chart(rsi_chart(hist_df, view_days),
                          use_container_width=True, config=_chart_config)
    except Exception as e:
        st.warning(f"Grafik çizilemedi: {e}")
    st.caption(CHART_CAPTION)

    # --- gerisi sekmelerde: tek anda tek bölüm, kalabalık scroll yok ---
    tab_ozet, tab_teknik, tab_temel, tab_bilanco, tab_puan, tab_not, tab_haber = st.tabs(
        ["📋 Özet", "📈 Teknik", "💰 Temel", "📊 Bilanço", "🧮 Puan Detayı",
         "📝 Notlar", "📰 Haberler"]
    )

    # --- özet profil (kar tanesi) + risk ---
    with tab_ozet:
        prof_col, risk_col = st.columns([1, 1])
        with prof_col:
            st.markdown("**❄️ Özet Profil**")
            sf = _render_snowflake(ev)
        with risk_col:
            st.markdown("**⚠️ Risk**")
            risk = _render_risk(hist_df, snap.market.value)

        st.markdown("**📐 İstikrar Profili**")
        st.caption(
            "Ne kadar oynak, trend ne kadar kalıcı, bilanço ne kadar sağlam — bu 'iyi "
            "hisse' etiketi değildir, sadece davranışın ne kadar öngörülebilir olduğunu "
            "tarif eder (kalıcı bir düşüş trendi de 'istikrarlı' sayılır)."
        )
        tech = ev.technical
        health = sf.values.get("Sağlık") if sf else None
        trend_age_txt = "—"
        if tech and tech.trend_age_days:
            trend_age_txt = f"~{tech.trend_age_days} gün · {tech.trend.value.lower()}"
        _metric_grid([
            ("Fiyat oynaklığı",
             f"%{risk.volatility_annual * 100:.0f}"
             if risk and risk.volatility_annual is not None else "—",
             badge_volatility(risk.level if risk else None)),
            ("Trend kalıcılığı", trend_age_txt,
             badge_trend_persistence(tech.trend_age_days if tech else None)),
            ("Finansal sağlamlık", f"{health:.0f}/100" if health is not None else "—",
             badge_health(health)),
        ])

    # --- teknik (trend gerekçesiyle) ---
    t = ev.technical
    with tab_teknik:
        if t is not None:
            st.markdown(f"**Teknik — Trend: {t.trend.value}**")
            st.info("\n".join(f"- {line}" for line in describe_trend(t)))

            trend_age = "—"
            if t.trend_age_days:
                trend_age = f"~{t.trend_age_days} işlem günü"
                if t.trend_age_days <= 10:
                    trend_age += " (taze)"
                if t.prior_trend is not None:
                    trend_age += f" · öncesinde {t.prior_trend.value.lower()}"

            cur = snap.currency or ""
            _metric_grid([
                (f"Son kapanış ({cur})".strip(), fmt_num(t.last_close), None),
                (f"SMA 50 ({cur})".strip(), fmt_num(t.sma_50), None),
                (f"SMA 200 ({cur})".strip(), fmt_num(t.sma_200), None),
                ("Trend yaşı", trend_age, None),
                ("RSI (14)", f"{fmt_num(t.rsi_14, 0)} ({t.rsi_zone.value})",
                 badge_rsi(t.rsi_14)),
                ("Kesişim", t.cross_signal or "yok", badge_cross(t.cross_signal)),
                ("Hacim / 20g ort.", f"{fmt_num(t.volume_ratio)}x" if t.volume_ratio else "—",
                 badge_volume(t.volume_ratio)),
            ])
            _terms_expander(["SMA 50 / 200", "RSI", "Hacim trendi"])
        else:
            st.caption("Teknik veri yok.")

    # --- temel ---
    f = ev.fundamentals
    with tab_temel:
        if f is not None:
            st.markdown("**Temel Analiz**")
            _metric_grid([
                ("F/K (12 ay)", fmt_num(f.pe_trailing), badge_pe(f.pe_trailing, snap.market)),
                ("F/K (beklenti)", fmt_num(f.pe_forward), badge_pe(f.pe_forward, snap.market)),
                ("PD/DD", fmt_num(f.price_to_book), badge_pb(f.price_to_book, snap.market)),
                ("Net kâr marjı", fmt_pct_frac(f.profit_margin), badge_margin(f.profit_margin)),
                ("Faaliyet marjı", fmt_pct_frac(f.operating_margin),
                 badge_margin(f.operating_margin)),
                ("ROE", fmt_pct_frac(f.return_on_equity), badge_roe(f.return_on_equity)),
                ("Borç/Özkaynak", fmt_num(f.debt_to_equity),
                 badge_debt_equity(f.debt_to_equity)),
                ("Cari oran", fmt_num(f.current_ratio), badge_current_ratio(f.current_ratio)),
                ("Temettü verimi", fmt_pct_frac(f.dividend_yield),
                 badge_dividend(f.dividend_yield)),
            ])
            _terms_expander(["F/K", "PD/DD", "Net kâr marjı", "Faaliyet marjı", "ROE",
                              "Borç/Özkaynak", "Cari oran", "Temettü verimi"])
        else:
            st.caption("Temel veri yok.")

    # --- bilanço karnesi (çok dönemli mali tablo) ---
    with tab_bilanco:
        _render_statements(snap.symbol)

    # --- puan kırılımı ---
    with tab_puan:
        if score is not None and score.reasons:
            st.markdown(f"**Puan kırılımı — {score.total}/100**  "
                        f"·  taban 50 · temel {score.fundamental:+d} "
                        f"· teknik {score.technical:+d}")
            st.dataframe({
                "Puan": [f"{r.points:+d}" for r in score.reasons],
                "Gerekçe": [r.label for r in score.reasons],
                "Kategori": [r.category for r in score.reasons],
            }, hide_index=True, use_container_width=True)
        else:
            st.caption("Puan kırılımı yok.")

    # --- notlar (yatırım günlüğü) ---
    with tab_not:
        _render_notes(snap.symbol)

    # --- haberler (yfinance; ABD'de dolu, BIST'te çoğunlukla boş) ---
    with tab_haber:
        render_news(
            ticker_news(symbol, 6),
            "Bu hisse için haber bulunamadı (yfinance BIST haberini sınırlı besliyor).",
            with_images=True,
        )

    st.caption("Bu çıktı yatırım tavsiyesi değildir; yalnızca araştırma amaçlıdır.")


def _render_notes(symbol: str) -> None:
    from src.ui.common import get_notes_repo

    repo = get_notes_repo()
    notes = repo.for_symbol(symbol)
    st.markdown(f"**📝 Notlar ({len(notes)})**")
    new = st.text_input("Not ekle", key=f"note_{symbol}",
                        placeholder="neden aldım / hedefim / bilanço sonrası bak...")
    if st.button("Ekle", key=f"note_add_{symbol}") and new.strip():
        repo.add(symbol, new)
        st.rerun()
    for n in notes:
        c1, c2 = st.columns([8, 1])
        c1.markdown(f"**{n.created_at[:10]}** — {n.text}")
        if c2.button("✕", key=f"note_del_{n.id}"):
            repo.delete(n.id)
            st.rerun()
