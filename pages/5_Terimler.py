"""Terim sözlüğü — src/glossary.py'den okur (CLI ile ortak kaynak)."""

from __future__ import annotations

import streamlit as st

from src.glossary import TERMS
from src.ui.common import page_header

page_header(
    "Terimler", "📖",
    "F/K, PD/DD, RSI, hareketli ortalama gibi göstergelerin ne anlama geldiğini "
    "kısaca açıklar.",
)

for t in TERMS:
    with st.expander(f"{t.key} — {t.name}"):
        st.markdown(f"**Nedir:** {t.what}")
        st.markdown(f"**Yorum:** {t.reading}")
