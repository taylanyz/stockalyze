"""
Veri sağlayıcı sözleşmesi (abstract base class).

ABC = Abstract Base Class = soyut temel sınıf.
Doğrudan örneği alınamaz; sadece "alt sınıflar şu metodları yazmak
ZORUNDA" diyen bir şablondur.

Kodun geri kalanı hep bu tipe bakar: "elimde bir MarketDataProvider var,
get_snapshot çağırırım, StockSnapshot alırım." Arkada yfinance mi,
İş Yatırım mı olduğu umurunda değil. Buna 'bağımlılığın tersine
çevrilmesi' (dependency inversion) denir — üst katman, alt katmanın
detayına değil ortak arayüze bağımlı.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.models import Fundamentals, StockSnapshot

if TYPE_CHECKING:
    # Sadece tip kontrolü için import; çalışma anında pandas'ı burada
    # yüklemek zorunda kalmayız (bu dosya hafif kalsın).
    import pandas as pd


class MarketDataProvider(ABC):
    """Tüm veri sağlayıcıların uyacağı arayüz."""

    @abstractmethod
    def get_snapshot(self, symbol: str) -> StockSnapshot:
        """
        Verilen sembol için anlık görüntüyü döndürür.

        Veri bulunamazsa ProviderError fırlatmalı (aşağıda tanımlı).
        Eksik ALAN varsa hata değil — ilgili alanı None bırak.
        """
        raise NotImplementedError

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """
        Verilen sembol için temel analiz oranlarını döndürür.

        Sembol tümüyle geçersizse ProviderError; oranların bir kısmı
        yoksa (BIST'te sık) ilgili alan None kalır.
        """
        raise NotImplementedError

    @abstractmethod
    def get_price_history(self, symbol: str, period: str = "2y") -> "pd.DataFrame":
        """
        Günlük fiyat/hacim geçmişini DataFrame olarak döndürür.

        Sütunlar: Open, High, Low, Close, Volume (tarih indeksli).
        Teknik göstergeler (SMA, RSI, hacim trendi) bu veriden hesaplanır.

        period: "1y", "2y", "5y", "max" gibi yfinance dönem kodu.
        Veri yoksa ProviderError.
        """
        raise NotImplementedError


class ProviderError(Exception):
    """Veri çekilirken oluşan hatalar için ortak tip (sembol yok, ağ hatası vb.)."""
