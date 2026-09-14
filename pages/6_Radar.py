"""
Radar — skoru iyi + ilgi gören hisseler + trend/konumlanma notu.

- BIST ve ABD ayrı bölümler (ilgi puanları kendi piyasası içinde kıyaslanır).
- Her piyasada iki liste: 'skoru iyi + ilgi gören' ve 'sadece ilgi gören'.
- Bir satıra tıkla → sağda o hissenin detay paneli açılır ('✕ Kapat' ile kapanır).
- Watchlist bölümünün üstünden hızlı sembol ekle/çıkar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis.radar import RadarRow
from src.config import add_to_watchlist, load_watchlist, remove_from_watchlist
from src.models import Market
from src.ui.common import fmt_num, fmt_pct, page_header, radar, score_emoji
from src.ui.detail import render_detail_panel

page_header(
    "Radar", "📡",
    "BIST 100 + ABD'nin en aktif hisseleri + watchlist'i tarar; bugünlerde "
    "skoru iyi ve ilgi gören hisseleri trend yorumuyla listeler.",
)

GOOD = 60          # bu skorun üstü "skoru iyi"
_SEL = "radar_selected"
_NONCE = "radar_nonce"
st.session_state.setdefault(_SEL, None)
st.session_state.setdefault(_NONCE, 0)

_TAG_ICON = {"olumlu": "🟢", "temkinli": "🟡", "riskli": "🔴", "notr": "⚪"}


def _close_detail() -> None:
    st.session_state[_SEL] = None
    st.session_state[_NONCE] += 1
    st.rerun()


def _df(rows: list[RadarRow]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Sembol": r.symbol,
            "Şirket": r.name,
            "Skor": f"{score_emoji(r.score)} {r.score}" if r.score is not None else "—",
            "İlgi": r.attention,
            "Gün %": fmt_pct(r.day_change_pct),
            "5g %": fmt_pct(r.ret_5d_pct),
            "Trend": r.trend.value,
            "RSI": fmt_num(r.rsi_14, 0),
            "Konumlanma notu": f"{_TAG_ICON.get(r.tag, '')} {r.note}",
        }
        for r in rows
    ])


def _table(rows: list[RadarRow], key: str) -> None:
    if not rows:
        st.caption("— yok —")
        return
    event = st.dataframe(
        _df(rows), hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row",
        key=f"{key}_{st.session_state[_NONCE]}",
        column_config={"Konumlanma notu": st.column_config.TextColumn(width="large")},
    )
    if event.selection.rows:
        sym = rows[event.selection.rows[0]].symbol
        if sym != st.session_state[_SEL]:
            st.session_state[_SEL] = sym
            st.rerun()


def _watchlist_editor() -> None:
    st.subheader("⭐ Watchlist durumu")
    st.caption("Konumlanma notu = **elde tutan** bakışı.")
    col_in, col_btn = st.columns([4, 1])
    new_sym = col_in.text_input(
        "Watchlist'e sembol ekle", key="wl_add", label_visibility="collapsed",
        placeholder="Sembol ekle (AAPL, THYAO.IS ...)",
    )
    if col_btn.button("➕ Ekle", use_container_width=True):
        if add_to_watchlist(new_sym):
            st.cache_data.clear()
            st.toast(f"{new_sym.upper()} eklendi")
            _close_detail()
        else:
            st.warning("Boş veya zaten listede.")

    wl = load_watchlist()
    if wl:
        chips = st.columns(min(len(wl), 6))
        for i, sym in enumerate(wl):
            if chips[i % 6].button(f"✕ {sym}", key=f"rm_{sym}"):
                remove_from_watchlist(sym)
                st.cache_data.clear()
                _close_detail()


def _render_radar(report) -> None:
    st.caption("Bir satıra tıkla → sağda o hissenin detay paneli açılır.")
    st.warning(
        "Konumlanma notları göstergelerin ne söylediğini tarif eder — "
        "**al/sat talimatı değildir.** İlgi = hacim artışı + günlük/haftalık hareket (0–100)."
    )
    c1, c2 = st.columns([1, 3])
    if c1.button("🔄 Yeniden tara"):
        st.cache_data.clear()
        _close_detail()
    only_good = c2.checkbox(
        f"Sadece skoru iyi olanları göster (≥ {GOOD})", value=False,
        help="İşaretliysen 'sadece ilgi gören' zayıf skorlu liste gizlenir.",
    )

    for market, label in ((Market.BIST, "🇹🇷 BIST"), (Market.US, "🇺🇸 ABD (NYSE / NASDAQ)")):
        rows = [r for r in report.hot if r.market is market]
        good = [r for r in rows if (r.score or 0) >= GOOD]
        weak = [r for r in rows if (r.score or 0) < GOOD]
        st.subheader(label)
        st.markdown(f"**Skoru iyi + ilgi gören** ({len(good)})")
        _table(good, f"good_{market.value}")
        if not only_good:
            st.markdown(f"**Sadece ilgi gören — skor < {GOOD}** ({len(weak)})")
            _table(weak, f"weak_{market.value}")

    st.divider()
    _watchlist_editor()
    _table(report.watchlist, "watch")


with st.spinner("Radar taranıyor (bulk indirme + değerlendirme, ~1 dk)..."):
    report = radar()

selected = st.session_state[_SEL]

if selected:
    left, right = st.columns([3, 2], gap="large")
    with left:
        _render_radar(report)
    with right:
        c_title, c_close = st.columns([2, 1])
        c_title.markdown("#### 📄 Detay")
        if c_close.button("✕ Kapat", use_container_width=True, key="close_detail",
                          help="Detayı kapat, tam radar görünümüne dön"):
            _close_detail()
        render_detail_panel(selected, compact=True)
else:
    _render_radar(report)
