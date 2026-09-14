"""Takvim — watchlist + portföy için yaklaşan temettü ve bilanço tarihleri."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import load_watchlist
from src.ui.common import calendar_events, get_portfolio_repo, page_header

page_header(
    "Takvim", "📅",
    "Watchlist ve portföyündeki hisselerin yaklaşan bilanço ve temettü (ex-date) "
    "tarihleri. Kaynak yfinance — BIST'te temettü tarihleri eksik olabilir.",
)

symbols = sorted(set(load_watchlist()) | set(get_portfolio_repo().symbols()))
if not symbols:
    st.info("Watchlist ve portföy boş — önce sembol ekle.")
    st.stop()

with st.spinner(f"{len(symbols)} hisse için takvim alınıyor..."):
    events = calendar_events(tuple(symbols))

_LABEL = {"earnings": "📊 Bilanço", "dividend": "💰 Temettü (ex-date)"}


def _table(kind: str) -> None:
    rows = [
        {
            "Tarih": e.event_date.strftime("%d.%m.%Y"),
            "Gün": f"{e.days_away:+d}" if e.days_away else "bugün",
            "Sembol": e.symbol,
            "Şirket": e.name,
            "Detay": e.detail or "—",
        }
        for e in events if e.kind == kind
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("Yaklaşan kayıt yok.")


tab1, tab2 = st.tabs(["📊 Bilanço takvimi", "💰 Temettü takvimi"])
with tab1:
    _table("earnings")
with tab2:
    _table("dividend")

st.caption("Yatırım tavsiyesi değildir.")
