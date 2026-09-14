"""
yfinance tabanlı veri sağlayıcı.

Şu an hem ABD hem BIST fiyat + temel verisini buradan çekiyoruz.
İleride BIST'in TEMEL verisi için ayrı bir sağlayıcı (İş Yatırım)
ekleyeceğiz; o zaman bu sınıf ABD için ana, BIST için sadece
fiyat/teknik kaynağı olarak kalacak.
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

# yfinance, sembol bulunamadığında ham HTTP hatasını ekrana döküyor.
# Biz zaten kendi temiz hata mesajımızı gösterdiğimiz için bunu susturuyoruz.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

from src.models import Fundamentals, Market, StockSnapshot
from src.providers.base import MarketDataProvider, ProviderError


def detect_market(symbol: str) -> Market:
    """
    Sembolden piyasayı tahmin et.

    yfinance'te BIST hisseleri ".IS" uzantısıyla gelir (THYAO.IS).
    Uzantı yoksa ABD borsası varsayıyoruz.
    """
    return Market.BIST if symbol.upper().endswith(".IS") else Market.US


class YFinanceProvider(MarketDataProvider):
    """MarketDataProvider sözleşmesinin yfinance ile uygulanması."""

    def __init__(self) -> None:
        # Basit istek-içi önbellek: aynı sembolün .info sözlüğünü bir kez
        # çekip saklarız. get_snapshot ve get_fundamentals arka arkaya
        # çağrıldığında yfinance'e iki kez gitmeyiz.
        # (Kalıcı/disk cache'i 5. adımda SQLite ile kuracağız.)
        self._info_cache: dict[str, dict] = {}

    # ---- iç yardımcılar ---------------------------------------------------

    def _get_info(self, symbol: str) -> dict:
        """Sembolün .info sözlüğünü (önbellekli) döndür."""
        if symbol not in self._info_cache:
            try:
                self._info_cache[symbol] = yf.Ticker(symbol).info or {}
            except Exception:
                self._info_cache[symbol] = {}
        return self._info_cache[symbol]

    # ---- MarketDataProvider sözleşmesi ----------------------------------

    def get_snapshot(self, symbol: str) -> StockSnapshot:
        symbol = symbol.strip().upper()
        ticker = yf.Ticker(symbol)

        # fast_info: hızlı ve güvenilir; fiyat/piyasa değeri için ilk tercih.
        fast = ticker.fast_info
        # info: yavaş ve bazen eksik; isim/sektör gibi "meta" bilgi için.
        info = self._get_info(symbol)

        price = (
            _safe_float(fast.get("last_price"))
            or _safe_float(info.get("currentPrice"))
            or _safe_float(info.get("regularMarketPrice"))   # döviz/emtia (=X, =F)
        )
        prev_close = _safe_float(fast.get("previous_close")) or _safe_float(
            info.get("previousClose")
        )
        if price is None and prev_close is not None:
            price = prev_close   # FX/futures'ta bazen sadece previousClose gelir

        # Hiç fiyat yoksa sembol muhtemelen geçersiz -> hata fırlat.
        if price is None and prev_close is None:
            raise ProviderError(f"'{symbol}' için veri bulunamadı (sembol yanlış olabilir).")

        day_change_pct = None
        if price is not None and prev_close:
            day_change_pct = (price - prev_close) / prev_close * 100

        return StockSnapshot(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            market=detect_market(symbol),
            currency=fast.get("currency") or info.get("currency"),
            price=price,
            previous_close=prev_close,
            day_change_pct=day_change_pct,
            market_cap=_safe_float(fast.get("market_cap")) or _safe_float(info.get("marketCap")),
            sector=info.get("sector"),
            exchange=fast.get("exchange") or info.get("exchange"),
        )

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        symbol = symbol.strip().upper()
        info = self._get_info(symbol)

        if not info:
            raise ProviderError(f"'{symbol}' için temel veri bulunamadı.")

        # yfinance debtToEquity'yi yüzde olarak verir (150.0 -> 1.5x).
        raw_de = _safe_float(info.get("debtToEquity"))
        debt_to_equity = raw_de / 100 if raw_de is not None else None

        # yfinance 1.7'de dividendYield ZATEN yüzde (KO -> 2.41 = %2.41).
        # Modelimizde tüm oranları kesir tutuyoruz, o yüzden 100'e bölüyoruz.
        raw_dy = _safe_float(info.get("dividendYield"))
        dividend_yield = raw_dy / 100 if raw_dy is not None else None

        return Fundamentals(
            symbol=symbol,
            pe_trailing=_safe_float(info.get("trailingPE")),
            pe_forward=_safe_float(info.get("forwardPE")),
            price_to_book=_safe_float(info.get("priceToBook")),
            profit_margin=_safe_float(info.get("profitMargins")),
            operating_margin=_safe_float(info.get("operatingMargins")),
            return_on_equity=_safe_float(info.get("returnOnEquity")),
            debt_to_equity=debt_to_equity,
            current_ratio=_safe_float(info.get("currentRatio")),
            dividend_yield=dividend_yield,
        )

    def get_price_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        symbol = symbol.strip().upper()
        # auto_adjust=True: temettü/bölünme etkisini fiyattan arındırır;
        # teknik analiz için "düzeltilmiş kapanış" istiyoruz.
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True)

        if df is None or df.empty:
            raise ProviderError(
                f"'{symbol}' için fiyat geçmişi bulunamadı (sembol yanlış olabilir)."
            )

        # Sadece ihtiyacımız olan sütunlar, tutarlı isimlerle.
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df


def _safe_float(value) -> float | None:
    """
    Gelen değeri float'a çevirmeyi dener; olmazsa None döner.
    yfinance bazen None, bazen boş string, bazen 'Infinity' döndürebiliyor —
    bu yardımcı hepsini tek noktada temizliyor.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):  # NaN / sonsuz kontrolü
        return None
    return result
