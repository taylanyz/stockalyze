"""
Veri modelleri.

Bu dosyadaki sınıflar sadece "veri taşır" — iş mantığı içermez.
Amaç: yfinance'ten (veya başka bir kaynaktan) gelen dağınık veriyi
tek tip, tahmin edilebilir bir nesneye çevirmek. Kodun geri kalanı
yfinance'in alan isimlerini değil, bu modeli tanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Market(str, Enum):
    """Hissenin işlem gördüğü piyasa. BIST ve ABD'yi ayrı değerlendireceğiz."""

    BIST = "BIST"
    US = "US"


@dataclass
class StockSnapshot:
    """
    Bir hissenin belirli bir andaki temel görüntüsü.

    'Snapshot' (anlık görüntü) diyoruz çünkü bu veri, aracı çalıştırdığın
    andaki durumu yansıtır — canlı akan bir veri değil.

    Alanların çoğu Optional (None olabilir): özellikle BIST hisselerinde
    bazı değerler gelmeyebilir. Bu durumda çökmek yerine None tutup
    ekranda "N/A" gösteririz.
    """

    symbol: str                      # yfinance sembolü, örn. "AAPL" / "THYAO.IS"
    name: str                        # şirket adı
    market: Market                   # BIST mi US mi
    currency: str | None             # fiyatın para birimi, örn. "USD" / "TRY"
    price: float | None              # güncel/son fiyat
    previous_close: float | None     # önceki kapanış (günlük değişim hesabı için)
    day_change_pct: float | None     # günlük yüzde değişim
    market_cap: float | None         # piyasa değeri
    sector: str | None               # sektör (ileride sektör-içi kıyas için)
    exchange: str | None             # borsa kodu, örn. "NMS", "IST"

    @property
    def is_up(self) -> bool:
        """Gün bazında yükselişte mi? (None ise False sayarız.)"""
        return (self.day_change_pct or 0) > 0


@dataclass
class Fundamentals:
    """
    Şirketin temel (mali) analiz oranları.

    StockSnapshot'tan ayrı tutuyoruz çünkü:
      - farklı kaynaktan gelebilir (BIST için ileride İş Yatırım),
      - farklı sıklıkta güncellenir (fiyat anlık, bilanço çeyreklik).

    Tüm alanlar Optional — veri gelmezse None, ekranda "N/A".

    Birim notları (yfinance ham verisini normalize ediyoruz):
      - Oranlar (marj, ROE): 0.25 = %25 gibi kesir olarak saklanır.
      - debt_to_equity: yfinance yüzde verir (150 -> 1.5x); biz katsayıya çeviririz.
    """

    symbol: str
    pe_trailing: float | None        # F/K (son 12 ay)
    pe_forward: float | None         # F/K (beklenti bazlı)
    price_to_book: float | None      # PD/DD
    profit_margin: float | None      # net kâr marjı (kesir)
    operating_margin: float | None   # faaliyet marjı (kesir)
    return_on_equity: float | None   # ROE (kesir)
    debt_to_equity: float | None     # borç/özkaynak (katsayı, ör. 1.5)
    current_ratio: float | None      # cari oran
    dividend_yield: float | None     # temettü verimi (kesir)


class Trend(str, Enum):
    """Fiyatın hareketli ortalamalara göre genel yönü."""

    UP = "Yükseliş"
    DOWN = "Düşüş"
    SIDEWAYS = "Yatay / Karışık"
    UNKNOWN = "Belirsiz"      # yeterli veri yok


class RSIZone(str, Enum):
    OVERBOUGHT = "Aşırı alım"     # RSI > 70
    NEUTRAL = "Nötr"
    OVERSOLD = "Aşırı satım"      # RSI < 30
    UNKNOWN = "Belirsiz"


@dataclass
class TechnicalIndicators:
    """
    Bir hissenin fiyat geçmişinden hesaplanan teknik göstergeler.

    Kaynak: provider.get_price_history() -> DataFrame.
    Hesaplama: analysis/technical.py (saf fonksiyonlar, I/O yok).

    Tüm sayısal alanlar Optional — yeterli geçmiş veri yoksa (yeni halka
    arz, veri boşluğu) None kalır, ekranda "N/A".
    """

    symbol: str
    as_of: str                       # verinin son günü (YYYY-MM-DD)
    data_points: int                 # hesaplamada kullanılan gün sayısı

    last_close: float | None
    sma_50: float | None
    sma_200: float | None
    price_vs_sma50_pct: float | None  # (fiyat - SMA50) / SMA50 * 100
    price_vs_sma200_pct: float | None

    trend: Trend
    cross_signal: str | None         # "Altın kesişim (12 gün önce)" gibi; yoksa None

    rsi_14: float | None
    rsi_zone: RSIZone

    volume_last: float | None
    volume_avg_20: float | None
    volume_ratio: float | None       # son hacim / 20g ortalama (1.5 = %50 fazla)

    # --- trendin "yolu" (tahmin değil, tarif) --------------------------
    trend_age_days: int | None = None      # bugünkü trend kaç işlem günüdür sürüyor
    prior_trend: "Trend | None" = None     # mevcut trend başlamadan önceki trend
    prior_return_pct: float | None = None  # önceki dönemde fiyat % değişimi


@dataclass
class StockEvaluation:
    """
    Bir hisseye dair TÜM toplanan veri, tek nesnede.

    Evaluator bunu üretir; app.py bunu tabloya/panele basar.
    Parçalardan herhangi biri None olabilir (o veri çekilemedi).
    error dolu ise hisse tümüyle değerlendirilemedi (ör. geçersiz sembol).
    """

    symbol: str
    snapshot: StockSnapshot | None = None
    fundamentals: Fundamentals | None = None
    technical: TechnicalIndicators | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """En azından fiyat verisi geldi mi?"""
        return self.error is None and self.snapshot is not None


@dataclass
class FinancialPeriod:
    """
    Bir raporlama dönemine ait mali tablo kalemleri.

    BIST: gelir tablosu kalemleri yıl-içi KÜMÜLATİF (period 3/6/9/12 = ay).
          Bilanço kalemleri o dönem sonu fotoğrafı.
    ABD:  yfinance yıllık tablosundan; period=12, is_annual=True.
    """

    label: str                       # "2024/12", "2025/6 (6 ay)"
    year: int
    period: int                      # 3 / 6 / 9 / 12
    is_annual: bool

    revenue: float | None = None
    gross_profit: float | None = None
    operating_profit: float | None = None
    ebitda: float | None = None
    net_income: float | None = None

    equity: float | None = None
    total_assets: float | None = None
    total_debt: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None

    operating_cash_flow: float | None = None

    @staticmethod
    def _ratio(num: float | None, den: float | None) -> float | None:
        return num / den if (num is not None and den) else None

    @property
    def net_margin(self) -> float | None:
        return self._ratio(self.net_income, self.revenue)

    @property
    def operating_margin(self) -> float | None:
        return self._ratio(self.operating_profit, self.revenue)

    @property
    def gross_margin(self) -> float | None:
        return self._ratio(self.gross_profit, self.revenue)

    @property
    def debt_to_equity(self) -> float | None:
        return self._ratio(self.total_debt, self.equity)

    @property
    def current_ratio(self) -> float | None:
        return self._ratio(self.current_assets, self.current_liabilities)


@dataclass
class FinancialHistory:
    """Bir hissenin son N dönemlik mali tablo geçmişi (Bilanço Karnesi)."""

    symbol: str
    currency: str | None
    source: str                      # "İş Yatırım" | "yfinance"
    periods: list[FinancialPeriod]   # eski -> yeni sıralı

    @property
    def latest(self) -> FinancialPeriod | None:
        return self.periods[-1] if self.periods else None
