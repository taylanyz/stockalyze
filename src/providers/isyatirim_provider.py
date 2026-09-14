"""
İş Yatırım tabanlı BIST temel veri sağlayıcısı.

Neden: yfinance BIST temel verisinde güvenilmez (THYAO'da PD/DD 18.6
gösteriyor, gerçek ~0.5). İş Yatırım'ın `MaliTablo` ucu tam bilanço +
gelir tablosu kalemlerini veriyor; oranları kendimiz hesaplıyoruz.

Kapsam (bilinçli olarak dar tutuldu):
  - Sadece XI_29 (sınai/hizmet) mali tablo formatı. Bankalar (UFRS)
    farklı kalem kodları kullanıyor -> onlarda İş Yatırım atlanır,
    Composite yfinance'e düşer.
  - Hesaplanan: F/K, PD/DD, ROE, net/faaliyet marjı, borç/özkaynak,
    cari oran. Temettü verimi İş Yatırım'da yok -> None (yfinance doldurur).

UYARI: `MaliTablo` belgelenmemiş bir uçtur; site değişirse kırılabilir.
Bu yüzden hata durumunda Composite sessizce yfinance'e döner.

Bu sınıf tam bir MarketDataProvider DEĞİLDİR — yalnızca temel veri üretir.
Composite onu fiyat/teknik için kullanmaz.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date

from src.models import Fundamentals
from src.providers.base import ProviderError

log = logging.getLogger(__name__)

_BASE = (
    "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/"
    "Data.aspx/MaliTablo"
)
_HEADERS = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
_GROUP = "XI_29"          # sınai/hizmet mali tablo formatı
_TIMEOUT = 20

# İhtiyacımız olan kalem kodları (MaliTablo itemCode).
_CURRENT_ASSETS = "1A"
_CURRENT_LIABILITIES = "2A"
_TOTAL_ASSETS = "1BL"
_TOTAL_EQUITY = "2N"          # azınlık dahil
_PARENT_EQUITY = "2O"        # ana ortaklığa ait
_REVENUE = "3C"
_OPERATING_PROFIT = "3DF"
_NET_INCOME = "3Z"           # ana ortaklık payları (dönem net kârı)

_REQUIRED = {_TOTAL_ASSETS, _PARENT_EQUITY, _REVENUE, _NET_INCOME}


def is_bist_symbol(symbol: str) -> bool:
    return symbol.strip().upper().endswith(".IS")


def bist_code(symbol: str) -> str:
    """THYAO.IS -> THYAO"""
    return symbol.strip().upper().removesuffix(".IS")


_code = bist_code   # geriye dönük iç kullanım


def _to_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN filtrele


def fetch_maltablo(code: str, year: int) -> dict[int, dict[str, float]]:
    """
    İş Yatırım MaliTablo — bir yılın tüm çeyrek sonlarını (12/9/6/3) çek.
    Dönüş: {period: {itemCode: value}}. Boş dönemler atılır.

    Hem BISTFundamentalsProvider hem StatementsProvider bunu kullanır.
    """
    periods = [12, 9, 6, 3]
    q = f"companyCode={code}&exchange=TRY&financialGroup={_GROUP}"
    for i, p in enumerate(periods, 1):
        q += f"&year{i}={year}&period{i}={p}"

    try:
        req = urllib.request.Request(f"{_BASE}?{q}", headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise ProviderError(f"İş Yatırım'a ulaşılamadı: {e}") from e

    if not data.get("ok") or not data.get("value"):
        return {}

    out: dict[int, dict[str, float]] = {p: {} for p in periods}
    for item in data["value"]:
        ic = item.get("itemCode")
        if not ic:
            continue
        for i, p in enumerate(periods, 1):
            v = _to_float(item.get(f"value{i}"))
            if v is not None:
                out[p][ic] = v
    return {p: d for p, d in out.items() if d}


class BISTFundamentalsProvider:
    """İş Yatırım MaliTablo -> Fundamentals (BIST, XI_29 formatı)."""

    def get_fundamentals(self, symbol: str, market_cap: float | None = None) -> Fundamentals:
        code = _code(symbol)
        year = date.today().year

        # İki çağrı: bu yıl ve geçen yıl, tüm çeyrek sonları (12/9/6/3).
        # Aralarında TTM için gereken her dönem bulunur.
        cur = self._fetch(code, year)
        prev = self._fetch(code, year - 1)

        # En güncel raporlanmış dönemi bul (bilanço = o günün fotoğrafı).
        latest_year, latest_period, bs = self._latest_period(cur, prev)
        if bs is None:
            raise ProviderError(f"{code}: İş Yatırım'da XI_29 mali tablo bulunamadı.")
        if not _REQUIRED.issubset(bs):
            # Muhtemelen banka (farklı format) -> İş Yatırım'ı kullanma.
            raise ProviderError(f"{code}: XI_29 formatına uymuyor (banka olabilir).")

        # Gelir tablosu kalemleri kümülatif -> TTM'e çevir.
        income_src = cur if latest_year == year else prev
        ttm_ni = self._ttm(income_src, prev, latest_year, latest_period, _NET_INCOME)
        ttm_rev = self._ttm(income_src, prev, latest_year, latest_period, _REVENUE)
        ttm_op = self._ttm(income_src, prev, latest_year, latest_period, _OPERATING_PROFIT)

        equity = bs.get(_PARENT_EQUITY)
        total_equity = bs.get(_TOTAL_EQUITY) or equity
        total_assets = bs.get(_TOTAL_ASSETS)
        cur_assets = bs.get(_CURRENT_ASSETS)
        cur_liab = bs.get(_CURRENT_LIABILITIES)

        def ratio(num, den):
            return num / den if (num is not None and den) else None

        return Fundamentals(
            symbol=symbol.upper(),
            pe_trailing=ratio(market_cap, ttm_ni) if (ttm_ni and ttm_ni > 0) else None,
            pe_forward=None,                                  # yfinance doldurur
            price_to_book=ratio(market_cap, equity),
            profit_margin=ratio(ttm_ni, ttm_rev),
            operating_margin=ratio(ttm_op, ttm_rev),
            return_on_equity=ratio(ttm_ni, equity),
            debt_to_equity=ratio((total_assets - total_equity) if
                                 (total_assets and total_equity) else None, equity),
            current_ratio=ratio(cur_assets, cur_liab),
            dividend_yield=None,                              # İş Yatırım'da yok
        )

    # ---- HTTP + parse -------------------------------------------------

    def _fetch(self, code: str, year: int) -> dict[int, dict[str, float]]:
        return fetch_maltablo(code, year)

    @staticmethod
    def _latest_period(
        cur: dict[int, dict], prev: dict[int, dict]
    ) -> tuple[int, int, dict | None]:
        """En güncel (yıl, dönem, bilanço-sözlüğü) üçlüsü."""
        this_year = date.today().year
        for period in (12, 9, 6, 3):
            if cur.get(period, {}).get(_PARENT_EQUITY) is not None:
                return this_year, period, cur[period]
        for period in (12, 9, 6, 3):
            if prev.get(period, {}).get(_PARENT_EQUITY) is not None:
                return this_year - 1, period, prev[period]
        return this_year, 0, None

    @staticmethod
    def _ttm(
        income_src: dict[int, dict],
        prev_year: dict[int, dict],
        latest_year: int,
        latest_period: int,
        code: str,
    ) -> float | None:
        """
        Kümülatif gelir tablosu kalemini son 12 aya çevir:
          TTM = cari_kümülatif(P) + geçen_yıl_tam(12) - geçen_yıl_kümülatif(P)
        P == 12 ise TTM doğrudan tam yıldır.
        """
        now = income_src.get(latest_period, {}).get(code)
        if now is None:
            return None
        if latest_period == 12:
            return now
        prev_full = prev_year.get(12, {}).get(code)
        prev_same = prev_year.get(latest_period, {}).get(code)
        if prev_full is None or prev_same is None:
            return now  # elde yeterli veri yok -> kısmi değeri döndür (yaklaşık)
        return now + prev_full - prev_same
