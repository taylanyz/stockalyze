"""
Hisse Analiz — web arayüzü giriş noktası.

Çalıştırma:
    streamlit run streamlit_app.py

Sayfa listesi + grup başlıkları burada tanımlanır (st.navigation).
Her sayfanın kendi içeriği pages/ altında; Ana Sayfa src/ui/home.py'de
fonksiyon olarak tutuluyor (giriş dosyası + sayfa aynı anda olamayacağı için).
Bu dosya ve pages/ altındakiler SADECE sunum. Tüm hesaplama
src/analysis, src/evaluator, src/providers içinde — CLI ile ortak.
"""

from __future__ import annotations

import streamlit as st

from src.ui.home import render_home

pg = st.navigation({
    "Genel Bakış": [
        st.Page(render_home, title="Ana Sayfa", icon="🏠", default=True),
    ],
    "🧭 Analiz": [
        st.Page("pages/1_Hisse_Detay.py", title="Hisse Detay", icon="🔍"),
        st.Page("pages/2_Karşılaştır.py", title="Karşılaştır", icon="⚖️"),
        st.Page("pages/6_Radar.py", title="Radar", icon="📡"),
        st.Page("pages/8_Tarama.py", title="Tarama", icon="🧮"),
    ],
    "💼 Takip & Portföy": [
        st.Page("pages/3_Watchlist.py", title="Watchlist", icon="⭐"),
        st.Page("pages/9_Portföy.py", title="Portföy", icon="💼"),
        st.Page("pages/12_Uyarılar.py", title="Uyarılar", icon="🔔"),
        st.Page("pages/4_Gün_Sonu.py", title="Gün Sonu", icon="🌇"),
        st.Page("pages/7_Snapshot_Değişim.py", title="Snapshot & Değişim", icon="🗓️"),
    ],
    "🌍 Piyasa": [
        st.Page("pages/10_Makro_Panel.py", title="Makro Panel", icon="🌍"),
        st.Page("pages/11_Takvim.py", title="Takvim", icon="📅"),
    ],
    "📖 Yardım": [
        st.Page("pages/5_Terimler.py", title="Terimler", icon="📖"),
    ],
})
pg.run()
