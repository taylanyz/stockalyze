"""Watchlist düzenleme + toplu değerlendirme."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import load_watchlist, save_watchlist
from src.ui.common import evaluate, fmt_num, fmt_pct, page_header, score_emoji
from src.ui.common import score as score_evaluation

page_header(
    "Watchlist", "⭐",
    "Takip ettiğin hisse listesini düzenlediğin ve tümünü tek seferde "
    "değerlendirdiğin yer.",
)

current = load_watchlist()

st.subheader("Listeyi düzenle")
raw = st.text_area(
    "Her satıra bir sembol (BIST için .IS)", value="\n".join(current), height=200,
)
if st.button("💾 Kaydet"):
    new = [s.strip().upper() for s in raw.splitlines() if s.strip()]
    save_watchlist(new)
    st.success(f"{len(new)} sembol kaydedildi.")
    st.cache_data.clear()
    current = new

st.divider()
st.subheader("Değerlendirme")

if not current:
    st.info("Liste boş. Yukarıdan sembol ekle.")
    st.stop()

with st.spinner("Değerlendiriliyor..."):
    evals = evaluate(tuple(current))

rows = []
for e in evals:
    if not e.ok:
        rows.append({"Sembol": e.symbol, "Şirket": "—", "Puan": "—", "Not": e.error})
        continue
    sc = score_evaluation(e)
    rows.append({
        "Sembol": e.symbol,
        "Şirket": e.snapshot.name,
        "Puan": f"{score_emoji(sc.total)} {sc.total}" if sc else "—",
        "Fiyat": f"{fmt_num(e.snapshot.price)} {e.snapshot.currency or ''}".strip(),
        "Gün %": fmt_pct(e.snapshot.day_change_pct),
        "Trend": e.technical.trend.value if e.technical else "—",
        "Not": sc.verdict if sc else "",
    })

df = pd.DataFrame(rows).sort_values(
    "Puan", ascending=False, key=lambda c: c.str.extract(r"(\d+)").fillna(-1).astype(int)[0]
)
st.dataframe(df, hide_index=True, use_container_width=True)
