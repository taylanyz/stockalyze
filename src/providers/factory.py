"""
Provider fabrikası — hangi sağlayıcı yığınının kurulacağını tek yerde toplar.

CLI ve Streamlit ortak kullanır.
"""

from __future__ import annotations

from src.providers.base import MarketDataProvider
from src.providers.composite import CompositeProvider
from src.storage.cache_provider import CachingProvider
from src.storage.database import Database


def build_provider(db: Database | None = None) -> MarketDataProvider:
    """
    CompositeProvider: fiyat/teknik -> yfinance, BIST temel -> İş Yatırım.
    db verilirse tüm yapı CachingProvider ile sarılır (decorator).
    """
    provider: MarketDataProvider = CompositeProvider()
    if db is not None:
        provider = CachingProvider(provider, db)
    return provider
