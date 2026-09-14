"""
Değerlendirme orkestrasyonu.

Bu katman "use case" (kullanım senaryosu) katmanıdır:
  - provider'dan (I/O) veri çeker,
  - analysis'e (hesaplama) verir,
  - sonucu tek bir StockEvaluation nesnesinde toplar.

app.py buradaki Evaluator'ı kullanır; provider/analysis detaylarıyla
doğrudan uğraşmaz.
"""

from __future__ import annotations

import logging

from src.analysis.technical import compute_technical
from src.models import StockEvaluation
from src.providers.base import MarketDataProvider, ProviderError

log = logging.getLogger(__name__)


class Evaluator:
    """Sembol(ler) için veri toplayıp StockEvaluation üretir."""

    def __init__(self, provider: MarketDataProvider) -> None:
        # Bağımlılık dışarıdan enjekte ediliyor (dependency injection):
        # test ederken sahte bir provider verebilirsin.
        self._provider = provider

    @property
    def provider(self) -> MarketDataProvider:
        """Alttaki sağlayıcı (ör. arayüzün fiyat grafiği için geçmiş çekmesi)."""
        return self._provider

    def evaluate(
        self,
        symbol: str,
        *,
        with_fundamentals: bool = True,
        with_technical: bool = True,
    ) -> StockEvaluation:
        """
        Tek sembolü değerlendir. Hiçbir zaman exception fırlatmaz —
        sorun olursa StockEvaluation.error dolu döner.
        """
        symbol = symbol.strip().upper()

        # Snapshot zorunlu: yoksa hisseyi hiç değerlendiremeyiz.
        try:
            snapshot = self._provider.get_snapshot(symbol)
        except ProviderError as exc:
            return StockEvaluation(symbol=symbol, error=str(exc))
        except Exception as exc:  # beklenmedik (ağ, kütüphane) hatası
            log.warning("get_snapshot(%s) beklenmedik hata: %s", symbol, exc)
            return StockEvaluation(symbol=symbol, error=f"Beklenmedik hata: {exc}")

        result = StockEvaluation(symbol=snapshot.symbol, snapshot=snapshot)

        # Temel ve teknik OPSİYONEL: patlarsa sadece o parça None kalır,
        # değerlendirme yine de kullanılabilir.
        if with_fundamentals:
            try:
                result.fundamentals = self._provider.get_fundamentals(symbol)
            except Exception as exc:
                log.info("get_fundamentals(%s) atlandı: %s", symbol, exc)

        if with_technical:
            try:
                history = self._provider.get_price_history(symbol)
                result.technical = compute_technical(snapshot.symbol, history)
            except Exception as exc:
                log.info("teknik analiz(%s) atlandı: %s", symbol, exc)

        return result

    def evaluate_many(
        self,
        symbols: list[str],
        *,
        with_fundamentals: bool = True,
        with_technical: bool = True,
    ) -> list[StockEvaluation]:
        """
        Birden çok sembolü değerlendir. Sıra korunur; tekrar edenler atılır.
        Bir sembolün hatası diğerlerini etkilemez.
        """
        seen: set[str] = set()
        ordered: list[str] = []
        for s in symbols:
            key = s.strip().upper()
            if key and key not in seen:
                seen.add(key)
                ordered.append(key)

        return [
            self.evaluate(
                s,
                with_fundamentals=with_fundamentals,
                with_technical=with_technical,
            )
            for s in ordered
        ]
