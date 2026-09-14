"""Tarama — evreni filtrele, kriterlere uyan hisseleri puana göre sırala."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis.screener import ScreenFilters, run_screener
from src.config import load_bist_universe, load_us_universe
from src.models import Market
from src.ui.common import (
    evaluate_universe,
    fmt_num,
    fmt_pct,
    fmt_pct_frac,
    page_header,
    refresh_sector_stats,
    score_emoji,
    sector_stats,
)
from src.ui.detail import render_detail_panel

page_header(
    "Tarama", "🔍",
    "Belirlediğin kriterlere (F/K, ROE, trend, puan...) uyan hisseleri evrenden "
    "süzüp puana göre sıralar.",
)

_ss = sector_stats()
_scol1, _scol2 = st.columns([3, 1])
if _ss:
    _scol1.caption(
        f"Sektörel puanlama açık — {len(_ss.get('sectors', {}))} sektör medyanı "
        f"(hesaplanma: {(_ss.get('computed_at') or '')[:10]}). "
        "F/K & PD/DD sektör medyanına göre puanlanıyor."
    )
else:
    _scol1.caption("Sektörel puanlama kapalı (medyan yok) — mutlak eşikler kullanılıyor.")
if _scol2.button("🔄 Sektör medyanlarını güncelle", help="~birkaç dk sürer"):
    with st.spinner("Evren geneli sektör medyanları hesaplanıyor..."):
        refresh_sector_stats()
    st.rerun()

_SEL = "screen_selected"
st.session_state.setdefault(_SEL, None)

# --- filtreler --------------------------------------------------------
with st.form("filtreler"):
    c1, c2, c3 = st.columns(3)
    with c1:
        mkts = st.multiselect("Piyasa", ["BIST", "ABD"], default=["BIST", "ABD"])
        min_score = st.slider("Min. puan", 0, 100, 60, 5)
        trends = st.multiselect("Trend", ["Yükseliş", "Yatay / Karışık", "Düşüş", "Belirsiz"],
                                default=["Yükseliş"])
    with c2:
        max_pe = st.number_input("Maks. F/K", 0.0, 500.0, 0.0, 1.0,
                                 help="0 = filtre yok")
        max_pb = st.number_input("Maks. PD/DD", 0.0, 100.0, 0.0, 0.5, help="0 = filtre yok")
        max_rsi = st.slider("Maks. RSI", 0, 100, 100, 5)
    with c3:
        min_roe = st.slider("Min. ROE %", 0, 60, 0, 5)
        min_margin = st.slider("Min. net marj %", -20, 60, 0, 5)
        min_div = st.slider("Min. temettü verimi %", 0, 15, 0, 1)
    run = st.form_submit_button("🔎 Tara", type="primary")

universe = tuple(
    (load_bist_universe() if "BIST" in mkts else [])
    + (load_us_universe() if "ABD" in mkts else [])
)

if not universe:
    st.info("En az bir piyasa seç.")
    st.stop()

filters = ScreenFilters(
    markets={Market.BIST} if mkts == ["BIST"] else
            {Market.US} if mkts == ["ABD"] else {Market.BIST, Market.US},
    min_score=min_score or None,
    max_pe=max_pe or None,
    max_pb=max_pb or None,
    min_roe=(min_roe / 100) or None,
    min_margin=(min_margin / 100) if min_margin else None,
    trends=set(trends) or None,
    max_rsi=float(max_rsi) if max_rsi < 100 else None,
    min_dividend=(min_div / 100) or None,
)

with st.spinner(f"{len(universe)} hisse değerlendiriliyor (ilk çalıştırma ~birkaç dk)..."):
    evals = evaluate_universe(universe)

hits = run_screener(evals, filters, sector_stats())

st.subheader(f"Sonuç: {len(hits)} hisse")
if not hits:
    st.caption("Kriterlere uyan hisse yok — filtreleri gevşet.")
    st.stop()

rows = []
for h in hits:
    e, f, t = h.ev, h.ev.fundamentals, h.ev.technical
    rows.append({
        "Sembol": e.symbol,
        "Şirket": e.snapshot.name,
        "Puan": f"{score_emoji(h.score)} {h.score}",
        "Fiyat": f"{fmt_num(e.snapshot.price)} {e.snapshot.currency or ''}".strip(),
        "F/K": fmt_num(f.pe_trailing) if f else "—",
        "PD/DD": fmt_num(f.price_to_book) if f else "—",
        "ROE": fmt_pct_frac(f.return_on_equity) if f else "—",
        "Temettü": fmt_pct_frac(f.dividend_yield) if f else "—",
        "Trend": t.trend.value if t else "—",
        "RSI": fmt_num(t.rsi_14, 0) if t else "—",
    })

event = st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     on_select="rerun", selection_mode="single-row", key="screen_tbl")
if event.selection.rows:
    sym = hits[event.selection.rows[0]].ev.symbol
    if sym != st.session_state[_SEL]:
        st.session_state[_SEL] = sym
        st.rerun()

if st.session_state[_SEL]:
    st.divider()
    c1, c2 = st.columns([4, 1])
    c1.markdown(f"#### 📄 {st.session_state[_SEL]}")
    if c2.button("✕ Kapat", use_container_width=True):
        st.session_state[_SEL] = None
        st.rerun()
    render_detail_panel(st.session_state[_SEL], compact=True)
