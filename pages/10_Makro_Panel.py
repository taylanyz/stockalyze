"""Makro Panel — tek bakışta piyasa nabzı (döviz, endeks, emtia, faiz)."""

from __future__ import annotations

import streamlit as st

from src.ui.common import fmt_num, fmt_pct, macro_metrics, page_header

page_header(
    "Makro Panel", "🌍",
    "Tek bakışta piyasa nabzı: USD/TRY, BIST 100, S&P 500, altın, petrol, VIX, "
    "dolar endeksi. Sadece bilgilendirme.",
)

with st.spinner("Piyasa verileri alınıyor..."):
    market, tcmb = macro_metrics()


def _cards(metrics, cols_per_row: int = 4) -> None:
    for i in range(0, len(metrics), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, m in zip(cols, metrics[i:i + cols_per_row]):
            with col:
                delta = fmt_pct(m.change_pct) if m.change_pct is not None else None
                col.metric(f"{m.name}", f"{fmt_num(m.value)} {m.unit}".strip(), delta)
                if m.history is not None and len(m.history) > 3:
                    col.line_chart(m.history.reset_index(drop=True), height=90)
                if m.week_change_pct is not None:
                    col.caption(f"1 hafta: {fmt_pct(m.week_change_pct)}")


st.subheader("Piyasalar")
_cards(market)

if tcmb:
    st.subheader("TCMB")
    _cards(tcmb, cols_per_row=3)
else:
    st.caption(
        "💡 TCMB verisi (politika faizi, enflasyon) için evds3.tcmb.gov.tr'den ücretsiz "
        "API key alıp `.streamlit/secrets.toml`'a `TCMB_EVDS_KEY = \"...\"` ekle "
        "(veya `data/evds_key.txt`)."
    )

st.divider()
st.caption(
    "Detaylı grafik/teknik için **Hisse Detay** sayfasına `USDTRY=X`, `GC=F` (altın), "
    "`BZ=F` (brent), `XU100.IS` (BIST 100) yazabilirsin. "
    "Veriler yfinance'ten, gecikmeli olabilir. Yatırım tavsiyesi değildir."
)
