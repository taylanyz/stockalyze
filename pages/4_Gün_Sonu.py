"""Gün sonu değerlendirmesi — bugünü kaydet, önceki kayıtla kıyasla."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config import load_watchlist
from src.ui.common import eod_report, fmt_num, fmt_pct, page_header, score_emoji

page_header(
    "Gün Sonu", "🌇",
    "Watchlist'i şu an değerlendirir, bugünün kaydını alır ve bir önceki kayıtla "
    "karşılaştırıp ne değiştiğini (puan + yeni sinyaller) özetler.",
)

wl = load_watchlist()
st.caption(f"Watchlist: {len(wl)} sembol · kıyas, veritabanındaki bir önceki kayda göre yapılır.")

if not wl:
    st.info("Watchlist boş — önce **Watchlist** sayfasından sembol ekle.")
    st.stop()

if not st.button("▶️ Gün sonu değerlendirmesini çalıştır", type="primary"):
    st.stop()

today = date.today().strftime("%Y-%m-%d")
with st.spinner("Değerlendiriliyor ve kaydediliyor..."):
    report, saved = eod_report(tuple(wl), today)

st.success(f"{saved} kayıt güncellendi ({today}).")

rows = []
for c in report.changes:
    rows.append({
        "Sembol": c.symbol,
        "Şirket": c.name,
        "Fiyat": f"{fmt_num(c.price)} {c.currency or ''}".strip(),
        "Gün %": fmt_pct(c.day_change_pct),
        "Skor": f"{score_emoji(c.score_now)} {c.score_now}",
        "Δ Skor": "—" if c.score_delta is None else f"{c.score_delta:+d}",
        "Yeni sinyaller": " · ".join(c.new_signals) if c.new_signals else "—",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

highlights = report.with_signals
if highlights:
    st.subheader("Öne çıkanlar")
    for c in highlights:
        st.markdown(f"**{c.symbol}** — " + "; ".join(c.new_signals))
else:
    st.caption("Bugün kayda değer yeni teknik sinyal yok.")

if report.failed:
    st.warning("Değerlendirilemeyenler: " + ", ".join(f"{s} ({e})" for s, e in report.failed))

if any(c.score_prev is None for c in report.changes):
    st.caption("Not: önceki kaydı olmayan hisselerde Δ Skor ilk günden sonra anlamlı.")
