"""Tek hisse detay sayfası — tüm içerik src/ui/detail.py'de (Radar da onu kullanır)."""

from __future__ import annotations

import streamlit as st

from src.ui.common import page_header
from src.ui.detail import render_detail_panel

page_header(
    "Hisse Detay", "🔍",
    "Tek bir hissenin fiyat grafiğini, temel + teknik göstergelerini ve "
    "gerekçeli puanını bir arada gösterir.",
)

symbol = st.text_input(
    "Hisse sembolü", value="AAPL",
    help="ABD: AAPL, MSFT ... · BIST: THYAO.IS, ASELS.IS ...",
).strip().upper()

if symbol:
    render_detail_panel(symbol)
