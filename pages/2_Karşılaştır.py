"""Çoklu hisse karşılaştırma sayfası — piyasaya göre gruplu, puana göre sıralı."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import load_watchlist
from src.models import Market
from src.ui.common import (
    evaluate,
    fmt_num,
    fmt_pct,
    fmt_pct_frac,
    page_header,
    score_emoji,
)
from src.ui.common import score as score_evaluation

page_header(
    "Karşılaştır", "⚖️",
    "Birden fazla hisseyi aynı tabloda yan yana koyar; puana göre sıralar, "
    "BIST ve ABD'yi ayrı gösterir.",
)

default = ", ".join(load_watchlist() or ["AAPL", "MSFT", "NVDA", "THYAO.IS", "ASELS.IS"])
raw = st.text_area("Semboller (virgül veya boşlukla ayır)", value=default, height=80)
symbols = tuple(s.strip().upper() for s in raw.replace(",", " ").split() if s.strip())

if not symbols:
    st.stop()

with st.spinner(f"{len(symbols)} sembol değerlendiriliyor..."):
    evals = evaluate(symbols)

ok = [e for e in evals if e.ok]
failed = [e for e in evals if not e.ok]


def table(rows) -> pd.DataFrame:
    scored = sorted(
        ((e, score_evaluation(e)) for e in rows),
        key=lambda t: t[1].total if t[1] else -1, reverse=True,
    )
    out = []
    for e, sc in scored:
        f, t = e.fundamentals, e.technical
        out.append({
            "Sembol": e.symbol,
            "Şirket": e.snapshot.name,
            "Puan": f"{score_emoji(sc.total)} {sc.total}" if sc else "—",
            "Fiyat": f"{fmt_num(e.snapshot.price)} {e.snapshot.currency or ''}".strip(),
            "Gün %": fmt_pct(e.snapshot.day_change_pct),
            "F/K": fmt_num(f.pe_trailing) if f else "—",
            "PD/DD": fmt_num(f.price_to_book) if f else "—",
            "ROE": fmt_pct_frac(f.return_on_equity) if f else "—",
            "Trend": t.trend.value if t else "—",
            "RSI": fmt_num(t.rsi_14, 0) if t else "—",
        })
    return pd.DataFrame(out)


for market, label in ((Market.BIST, "BIST"), (Market.US, "ABD (NYSE / NASDAQ)")):
    group = [e for e in ok if e.snapshot.market is market]
    if group:
        cur = group[0].snapshot.currency or ("TRY" if market is Market.BIST else "USD")
        st.subheader(f"{label}  ·  fiyatlar {cur}")
        st.dataframe(table(group), hide_index=True, use_container_width=True)

if failed:
    st.warning("Değerlendirilemeyenler: " + ", ".join(f"{e.symbol} ({e.error})" for e in failed))
