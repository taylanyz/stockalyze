"""
Radar — en aktif/ilgi gören hisseler + puan + trend/konumlanma notu.

- BIST ve ABD ayrı bölümler (ilgi puanları kendi piyasası içinde kıyaslanır).
- Her piyasada tek tablo; "sadece skoru iyi olanları göster" tiki ile filtrelenir.
- Bir satıra tıkla → sağda o hissenin detay paneli açılır ('✕ Kapat' ile kapanır).
- Watchlist bölümünün üstünden hızlı sembol ekle/çıkar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis.radar import RadarRow
from src.config import add_to_watchlist, load_watchlist, remove_from_watchlist
from src.glossary import TERMS_BY_KEY
from src.models import Market
from src.ui.common import fmt_num, fmt_pct, page_header, radar, score_emoji
from src.ui.detail import render_detail_panel
from src.ui.explain import TAG_ICON

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
            "Konumlanma notu": f"{TAG_ICON.get(r.tag, '')} {r.note}",
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


def _explainer() -> None:
    with st.expander("📖 Puan ve İlgi ne anlama geliyor?"):
        puan, ilgi = TERMS_BY_KEY["Puan"], TERMS_BY_KEY["İlgi"]
        st.markdown(f"**{puan.name}** — {puan.what}  \n*Nasıl okunur:* {puan.reading}")
        st.markdown(f"**{ilgi.name}** — {ilgi.what}  \n*Nasıl okunur:* {ilgi.reading}")
        st.markdown(
            "**Bu ikisini birlikte okumak:**\n"
            "- 🟢 **Yüksek puan + yüksek ilgi** — hem temel/teknik görünüm iyi hem de "
            "piyasa şu an bu hisseyle ilgileniyor. Genelde yakından bakmaya değer liste budur.\n"
            "- 🟡 **Düşük puan + yüksek ilgi** — hisse çok işlem görüyor/hareketli ama "
            "puanı düşük: genelde spekülatif hareket, bir haber ya da söylentiden "
            "kaynaklanıyor olabilir. Fiyat hareketi ile şirketin temelleri örtüşmüyor demektir.\n"
            "- 🔴 **Sert düşüş + yüksek ilgi** — İlgi puanı yön gözetmez, sert düşüşler de "
            "hacim/hareket getirir. Bu durumda 'ilgi' aslında panik satışı olabilir — "
            "Gün %/5g % sütunlarına mutlaka bak.\n"
            "- ⚪ **Yüksek puan + düşük ilgi** — temelleri iyi ama şu an kimse "
            "ilgilenmiyor; sakin/gözden kaçmış olabilir."
        )


def _render_radar(report) -> None:
    st.caption("Bir satıra tıkla → sağda o hissenin detay paneli açılır.")
    st.warning(
        "Konumlanma notları göstergelerin ne söylediğini tarif eder — "
        "**al/sat talimatı değildir.** İlgi = hacim artışı + günlük/haftalık hareket (0–100)."
    )
    _explainer()
    c1, c2 = st.columns([1, 3])
    if c1.button("🔄 Yeniden tara"):
        st.cache_data.clear()
        _close_detail()
    only_good = c2.checkbox(
        f"Sadece skoru iyi olanları göster (≥ {GOOD})", value=False,
        help="İşaretliysen skoru düşük olan satırlar tablodan gizlenir.",
    )

    for market, label in ((Market.BIST, "🇹🇷 BIST"), (Market.US, "🇺🇸 ABD (NYSE / NASDAQ)")):
        rows = [r for r in report.hot if r.market is market]
        if only_good:
            rows = [r for r in rows if (r.score or 0) >= GOOD]
        st.subheader(f"{label} ({len(rows)})")
        _table(rows, f"tbl_{market.value}")

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
