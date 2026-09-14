"""Uyarılar — koşullu kurallar tanımla, tetiklenenleri gör."""

from __future__ import annotations

import streamlit as st

from src.config import load_watchlist
from src.storage.alerts_repo import KINDS
from src.ui.common import (
    check_pending_alerts,
    get_alerts_repo,
    get_portfolio_repo,
    page_header,
)

page_header(
    "Uyarılar", "🔔",
    "Koşul tanımla (RSI, fiyat, puan, kesişim); tetiklenen uyarıları burada ve "
    "her sayfanın üstünde gör.",
)

repo = get_alerts_repo()

# --- kural ekle -----------------------------------------------------
sym_options = sorted(set(load_watchlist()) | set(get_portfolio_repo().symbols()))
with st.form("kural"):
    c1, c2, c3 = st.columns([2, 3, 1])
    sym = c1.selectbox("Sembol", sym_options) if sym_options else c1.text_input("Sembol")
    kind = c2.selectbox("Koşul", list(KINDS), format_func=lambda k: KINDS[k])
    thr = c3.number_input("Eşik", value=0.0, step=1.0,
                          help="golden_cross için boş bırak")
    if st.form_submit_button("➕ Kural ekle", type="primary") and sym:
        repo.add(sym, kind, None if kind == "golden_cross" else thr)
        st.rerun()

# --- tetiklenenler ------------------------------------------------
with st.spinner("Kurallar kontrol ediliyor..."):
    triggered, _ = check_pending_alerts()

if triggered:
    st.subheader("🔴 Tetiklenen uyarılar")
    for t in triggered:
        st.error(f"**{t.symbol}** — {t.message}")
else:
    st.success("Şu an tetiklenen uyarı yok.")

# --- kural listesi ----------------------------------------------
rules = repo.all()
st.subheader(f"Kurallar ({len(rules)})")
if not rules:
    st.caption("Henüz kural yok.")
for r in rules:
    c1, c2, c3 = st.columns([6, 1, 1])
    c1.markdown(("✅ " if r.active else "⏸️ ") + r.describe()
                + (f"  ·  son tetik: {r.last_fired}" if r.last_fired else ""))
    if c2.button("⏸️" if r.active else "▶️", key=f"tg_{r.id}"):
        repo.toggle(r.id, not r.active)
        st.rerun()
    if c3.button("✕", key=f"rm_{r.id}"):
        repo.delete(r.id)
        st.rerun()

st.divider()
st.caption(
    "**Otomatik kontrol:** Windows Görev Zamanlayıcı ile `python -m src.app "
    "--check-alerts` komutunu günde birkaç kez çalıştır — tetiklenenler "
    "`data/alerts.json`'a yazılır."
)
