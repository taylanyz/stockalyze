"""
Snapshot & Değişim — watchlist'in günlük fotoğrafını al, iki günü karşılaştır.

Akış:
  1. Bugün 'Snapshot al' → watchlist değerlendirilip o günün tarihiyle DB'ye yazılır.
  2. Yarın (veya sonra) yine snapshot al.
  3. İki tarih seç → 'Karşılaştır' → puan değişimi + yeni teknik sinyaller.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config import load_watchlist
from src.ui.common import (
    compare_snapshots,
    fmt_num,
    page_header,
    score_emoji,
    snapshot_dates,
    take_snapshot,
)

page_header(
    "Snapshot & Değişim", "🗓️",
    "Watchlist'in günlük 'fotoğrafını' kaydeder; farklı günlerin kayıtlarını "
    "karşılaştırıp puan ve teknik sinyal değişimlerini gösterir.",
)

wl = load_watchlist()
today = date.today().strftime("%Y-%m-%d")

# --- 1) snapshot al --------------------------------------------------
st.subheader("📸 Snapshot al")
st.caption(
    f"Watchlist'teki {len(wl)} hissenin **bu anki** durumunu bugünün tarihiyle "
    f"({today}) veritabanına kaydeder. Aynı gün tekrar alırsan üzerine yazar."
)
if st.button("📸 Bugünün snapshot'ını al", type="primary", disabled=not wl):
    with st.spinner("Değerlendiriliyor ve kaydediliyor..."):
        n = take_snapshot(tuple(wl), today)
    st.success(f"{n} kayıt yazıldı ({today}).")
    st.cache_data.clear()
if not wl:
    st.info("Watchlist boş — **Watchlist** veya **Radar** sayfasından sembol ekle.")

# --- kayıtlı günler tablosu ---------------------------------------
dates = snapshot_dates()
st.subheader("📅 Kayıtlı snapshot günleri")
if dates:
    st.dataframe(
        pd.DataFrame(dates, columns=["Tarih", "Sembol sayısı"]),
        hide_index=True, use_container_width=True,
    )
else:
    st.caption("Henüz snapshot yok.")

# --- 2) karşılaştır -----------------------------------------------
st.subheader("🔍 Dünden bugüne — değişim analizi")
if len(dates) < 2:
    st.info("Karşılaştırma için en az 2 farklı günde snapshot gerekir.")
    st.stop()

all_dates = [d for d, _ in dates]
c1, c2 = st.columns(2)
d_new = c1.selectbox("Yeni tarih", all_dates, index=0)
older = [d for d in all_dates if d < d_new] or all_dates[1:]
d_old = c2.selectbox("Eski tarih", older, index=0)

report = compare_snapshots(d_new, d_old)
rows = [
    {
        "Sembol": c.symbol,
        "Şirket": c.name,
        "Fiyat": f"{fmt_num(c.price)} {c.currency or ''}".strip(),
        "Skor": f"{score_emoji(c.score_now)} {c.score_now}",
        "Δ Skor": "—" if c.score_delta is None else f"{c.score_delta:+d}",
        "Yeni sinyaller": " · ".join(c.new_signals) if c.new_signals else "—",
    }
    for c in report.changes
]
st.markdown(f"**{d_old} → {d_new}**")
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
             column_config={"Yeni sinyaller": st.column_config.TextColumn(width="large")})

hl = report.with_signals
if hl:
    st.markdown("**Öne çıkanlar (yeni sinyal olanlar):**")
    for c in hl:
        st.markdown(f"- **{c.symbol}** — " + "; ".join(c.new_signals))
else:
    st.caption("Bu iki gün arasında kayda değer yeni teknik sinyal yok.")

# --- değişim akışı (tüm günler) --------------------------------
st.divider()
st.subheader("📰 Değişim Akışı")
st.caption("Tüm kayıtlı günler boyunca watchlist'inde ne değiştiğinin zaman çizelgesi.")
from src.analysis.eod import change_feed  # noqa: E402
from src.ui.common import get_repo  # noqa: E402

feed = change_feed(get_repo())
if not feed:
    st.caption("Henüz akış oluşacak kadar snapshot yok (en az 2 gün gerekir).")
else:
    cur = None
    for e in feed:
        if e.date != cur:
            cur = e.date
            st.markdown(f"**{e.date}**")
        st.markdown(f"- {e.symbol} — {e.text}")

st.divider()
st.caption(
    "**Otomatik snapshot?** Her gün elle almak yerine Windows Görev Zamanlayıcı ile "
    "`python -m src.app --eod` komutunu günde bir çalıştırabilirsin (bilgisayar açıksa "
    "yeter, sunucu gerekmez). Bulutta çalışması için ayrı bir zamanlayıcı servisi gerekir."
)
