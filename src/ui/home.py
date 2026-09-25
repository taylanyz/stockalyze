"""Ana Sayfa içeriği — st.navigation üzerinden çağrılan sayfa fonksiyonu."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import load_bist_universe
from src.providers.screener import Mover
from src.ui.common import (
    fmt_count,
    fmt_num,
    fmt_pct,
    market_news,
    page_header,
    render_news,
    trending,
)


def _movers_df(movers: list[Mover]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Sembol": m.symbol,
            "Şirket": m.name,
            "Fiyat": f"{fmt_num(m.price)} {m.currency or ''}".strip(),
            "Gün %": fmt_pct(m.day_change_pct),
            "Hacim": fmt_count(m.volume),
        }
        for m in movers
    ])


def _section(title: str, groups: dict[str, list[Mover]]) -> None:
    st.subheader(title)
    c1, c2, c3 = st.columns(3)
    for col, key, label in (
        (c1, "gainers", "📈 En çok yükselenler"),
        (c2, "losers", "📉 En çok düşenler"),
        (c3, "actives", "🔊 En çok işlem görenler"),
    ):
        with col:
            st.markdown(f"**{label}**")
            rows = groups.get(key) or []
            if rows:
                st.dataframe(_movers_df(rows), hide_index=True, use_container_width=True)
            else:
                st.caption("Veri yok")


def render_home() -> None:
    page_header(
        "Ana Sayfa — Piyasada Ne Hareketleniyor", "🏠",
        "Bugün piyasada en çok yükselen, düşen ve işlem gören hisseleri gösterir "
        "(watchlist'ten bağımsız — genel piyasa görünümü).",
    )

    universe = load_bist_universe()

    col1, col2 = st.columns([3, 1])
    with col2:
        count = st.slider("Liste uzunluğu", 5, 25, 12)
        if st.button("🔄 Yenile"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Piyasa taranıyor..."):
        report = trending(tuple(universe), count=count)

    _section("ABD (NYSE / NASDAQ)  ·  fiyatlar USD", report.us)
    st.divider()
    _section(f"BIST ({len(universe)} hisselik evren)  ·  fiyatlar TRY", report.bist)

    st.divider()
    st.subheader("📰 Piyasa Haberleri")
    st.caption(
        "Türkçe finans kaynaklarından (Investing TR, Dünya, Bloomberg HT) son başlıklar. "
        "Sadece bilgilendirme — puanlamayı etkilemez, içerik analiz edilmez."
    )
    with st.spinner("Haberler alınıyor..."):
        news = market_news(16)
    render_news(news, "Haber alınamadı (kaynaklara ulaşılamadı).", columns=2)

    st.divider()
    st.info(
        "Bir hisseye yakından bakmak için soldaki **Hisse Detay** sayfasını kullan. "
        "Terimlerin anlamı için **Terimler** sayfasına bak."
    )
