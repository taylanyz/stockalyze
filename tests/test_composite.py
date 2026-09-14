"""
Composite + İş Yatırım saf mantık testleri (ağ yok).

Ağ çağrısı yapan kısımlar (get_fundamentals uçtan uca) burada test
edilmez — onlar entegrasyon testi konusu. Burada birleştirme ve
TTM matematiği gibi saf parçalar var.
"""

from __future__ import annotations

from src.models import Fundamentals
from src.providers.composite import _merge_fundamentals
from src.providers.isyatirim_provider import BISTFundamentalsProvider, _code, is_bist_symbol


def _f(**kw) -> Fundamentals:
    base = dict(
        symbol="X", pe_trailing=None, pe_forward=None, price_to_book=None,
        profit_margin=None, operating_margin=None, return_on_equity=None,
        debt_to_equity=None, current_ratio=None, dividend_yield=None,
    )
    base.update(kw)
    return Fundamentals(**base)


def test_merge_isyatirim_bozuk_yfinance_i_ezer():
    isy = _f(price_to_book=0.4, debt_to_equity=1.3)
    yf = _f(price_to_book=18.6, dividend_yield=0.02, pe_forward=4.1)
    merged = _merge_fundamentals(primary=isy, fallback=yf)
    assert merged.price_to_book == 0.4          # İş Yatırım kaldı
    assert merged.dividend_yield == 0.02        # yfinance doldurdu
    assert merged.pe_forward == 4.1


def test_merge_fallback_yoksa_primary_doner():
    isy = _f(price_to_book=0.4)
    assert _merge_fundamentals(isy, None) is isy


def test_sembol_yardimcilari():
    assert is_bist_symbol("THYAO.IS")
    assert not is_bist_symbol("AAPL")
    assert _code("thyao.is") == "THYAO"


def test_ttm_tam_yil_dogrudan_doner():
    src = {12: {"3Z": 100.0}}
    out = BISTFundamentalsProvider._ttm(src, {}, 2025, 12, "3Z")
    assert out == 100.0


def test_ttm_ara_donem_hesabi():
    # cari 6 aylık = 60, geçen yıl tam = 100, geçen yıl 6 aylık = 40
    # TTM = 60 + 100 - 40 = 120
    cur = {6: {"3Z": 60.0}}
    prev = {12: {"3Z": 100.0}, 6: {"3Z": 40.0}}
    out = BISTFundamentalsProvider._ttm(cur, prev, 2025, 6, "3Z")
    assert out == 120.0
