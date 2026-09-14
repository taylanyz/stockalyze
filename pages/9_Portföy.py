"""Portföy — pozisyonları gir, güncel değer / K-Z / dağılım / risk gör."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis.portfolio import build_portfolio
from src.storage.portfolio_repo import Position
from src.ui.common import (
    evaluate,
    fmt_num,
    fmt_pct,
    fmt_trim,
    get_portfolio_repo,
    page_header,
    score_emoji,
    sector_stats,
)

page_header(
    "Portföy", "💼",
    "Elindeki hisseleri (adet + alış fiyatı) gir; güncel değer, kâr/zarar, "
    "sektör dağılımı ve ağırlıklı puanı gör.",
)

repo = get_portfolio_repo()
positions = repo.all()

# --- pozisyon ekle/güncelle -----------------------------------------
with st.expander("➕ Pozisyon ekle / güncelle", expanded=not positions):
    with st.form("pos"):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
        sym = c1.text_input("Sembol", placeholder="THYAO.IS").strip().upper()
        qty = c2.number_input("Adet", min_value=0.0, step=0.00001, format="%.5f")
        buy = c3.number_input("Alış fiyatı", min_value=0.0, step=0.00001, format="%.5f")
        bdate = c4.date_input("Alış tarihi", value=date.today())
        note = st.text_input("Not (opsiyonel)")
        if st.form_submit_button("Kaydet", type="primary"):
            if sym and qty > 0 and buy > 0:
                repo.upsert(Position(sym, qty, buy, bdate.strftime("%Y-%m-%d"), note or None))
                st.success(f"{sym} kaydedildi.")
                st.rerun()
            else:
                st.warning("Sembol, adet ve alış fiyatı gerekli.")

if not positions:
    st.info("Henüz pozisyon yok — yukarıdan ekle.")
    st.stop()

# çıkar butonları
st.caption("Çıkarmak için:")
chips = st.columns(min(len(positions), 6))
for i, p in enumerate(positions):
    if chips[i % 6].button(f"✕ {p.symbol}", key=f"del_{p.symbol}"):
        repo.delete(p.symbol)
        st.rerun()

# --- değerlendir + özet -------------------------------------------
with st.spinner("Portföy değerlendiriliyor..."):
    evals = {e.symbol: e for e in evaluate(tuple(p.symbol for p in positions))}
summary = build_portfolio(positions, evals, sector_stats())

if len(summary.currencies) > 1:
    st.warning(
        "Portföyde farklı para birimleri var (" + ", ".join(sorted(summary.currencies)) +
        "). Toplamlar kur çevrimi yapılmadan **yaklaşık** hesaplanır."
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Toplam değer", fmt_num(summary.total_value))
m2.metric("Toplam K/Z", fmt_num(summary.total_pnl),
          fmt_pct(summary.total_pnl_pct * 100 if summary.total_pnl_pct is not None else None))
m3.metric("Ağırlıklı puan",
          f"{score_emoji(round(summary.weighted_score))} {summary.weighted_score:.0f}"
          if summary.weighted_score is not None else "—")
m4.metric("Tahmini yıllık temettü", fmt_num(summary.est_annual_dividend))

# --- pozisyon tablosu -------------------------------------------
rows = []
for h in summary.holdings:
    rows.append({
        "Sembol": h.symbol,
        "Şirket": h.name,
        "Adet": fmt_trim(h.quantity, 8, 0),
        "Alış": f"{fmt_trim(h.buy_price, 8, 2)} {h.currency or ''}".strip(),
        "Güncel": f"{fmt_trim(h.price, 8, 2)} {h.currency or ''}".strip(),
        "Değer": fmt_num(h.value),
        "K/Z": fmt_num(h.pnl),
        "K/Z %": fmt_pct(h.pnl_pct * 100 if h.pnl_pct is not None else None),
        "Ağırlık": fmt_pct((h.value / summary.total_value) * 100
                           if (h.value and summary.total_value) else None),
        "Puan": f"{score_emoji(h.score)} {h.score}" if h.score is not None else "—",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

if summary.missing:
    st.caption("Değerlendirilemeyen: " + ", ".join(summary.missing))

# --- sektör dağılımı -------------------------------------------
weights = summary.sector_weights
if weights:
    st.subheader("Sektör dağılımı")
    fig = go.Figure(go.Pie(labels=list(weights), values=list(weights.values()), hole=0.45))
    fig.update_layout(title=dict(text="Değere göre sektör ağırlıkları", font=dict(size=12)),
                      height=320, margin=dict(l=10, r=10, t=36, b=10))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
