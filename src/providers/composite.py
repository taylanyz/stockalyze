"""
Bileşik sağlayıcı (Composite deseni).

Sembole göre farklı kaynakları birleştirir:
  - Fiyat / anlık görüntü / fiyat geçmişi  -> her zaman yfinance
  - Temel veri:
      * ABD  -> yfinance
      * BIST -> İş Yatırım (öncelikli) + yfinance (eksikleri doldurur)

Evaluator bunu tek bir MarketDataProvider olarak görür; hangi verinin
nereden geldiğini bilmez.
"""

from __future__ import annotations

import logging
from dataclasses import replace

import pandas as pd

from src.models import Fundamentals
from src.providers.base import MarketDataProvider, ProviderError
from src.providers.isyatirim_provider import BISTFundamentalsProvider, is_bist_symbol
from src.providers.yfinance_provider import YFinanceProvider

log = logging.getLogger(__name__)

# İş Yatırım'dan gelmesi beklenen (ve yfinance'te BIST için bozuk olan) alanlar.
_ISY_FIELDS = (
    "pe_trailing", "price_to_book", "profit_margin", "operating_margin",
    "return_on_equity", "debt_to_equity", "current_ratio",
)


def _merge_fundamentals(primary: Fundamentals, fallback: Fundamentals | None) -> Fundamentals:
    """primary'deki None alanları fallback'ten doldur."""
    if fallback is None:
        return primary
    patch = {
        f: getattr(fallback, f)
        for f in _ISY_FIELDS + ("pe_forward", "dividend_yield")
        if getattr(primary, f) is None and getattr(fallback, f) is not None
    }
    return replace(primary, **patch) if patch else primary


class CompositeProvider(MarketDataProvider):
    def __init__(
        self,
        yfinance: YFinanceProvider | None = None,
        bist_fundamentals: BISTFundamentalsProvider | None = None,
    ) -> None:
        self._yf = yfinance or YFinanceProvider()
        self._bist = bist_fundamentals or BISTFundamentalsProvider()

    # ---- fiyat tarafı: doğrudan yfinance ---------------------------

    def get_snapshot(self, symbol: str):
        return self._yf.get_snapshot(symbol)

    def get_price_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        return self._yf.get_price_history(symbol, period)

    # ---- temel veri: kaynağa göre --------------------------------

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        if not is_bist_symbol(symbol):
            return self._yf.get_fundamentals(symbol)

        # BIST: yfinance'i taban al (temettü, forward F/K için), İş Yatırım'ı üzerine koy.
        yf_fund: Fundamentals | None = None
        try:
            yf_fund = self._yf.get_fundamentals(symbol)
        except Exception as e:
            log.info("yfinance temel veri (%s) alınamadı: %s", symbol, e)

        try:
            market_cap = self._yf.get_snapshot(symbol).market_cap
            isy_fund = self._bist.get_fundamentals(symbol, market_cap=market_cap)
            return _merge_fundamentals(primary=isy_fund, fallback=yf_fund)
        except ProviderError as e:
            log.info("İş Yatırım atlandı (%s): %s — yfinance'e dönülüyor", symbol, e)
        except Exception as e:  # beklenmedik (uç değişti, parse hatası)
            log.warning("İş Yatırım beklenmedik hata (%s): %s", symbol, e)

        if yf_fund is None:
            raise ProviderError(f"{symbol}: temel veri hiçbir kaynaktan alınamadı.")
        return yf_fund
