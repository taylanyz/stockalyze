"""risk.py + snowflake.py saf mantık testleri (ağ yok)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.risk import compute_risk, describe_risk
from src.analysis.snowflake import compute_snowflake
from src.models import Fundamentals, StockEvaluation, StockSnapshot, Market


def _price_df(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="B")
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                         "Close": closes, "Volume": [1e6] * len(closes)}, index=idx)


def test_risk_sabit_fiyat_sifir_volatilite():
    r = compute_risk(_price_df([100.0] * 60))
    assert r.volatility_annual == 0.0
    assert r.max_drawdown == 0.0


def test_risk_dususte_max_drawdown_negatif():
    closes = list(np.linspace(100, 60, 80))
    r = compute_risk(_price_df(closes))
    assert r.max_drawdown < -0.35
    assert "düşüş" in " ".join(describe_risk(r))


def test_risk_beta_endeksle_ayni_hareket():
    base = list(np.linspace(100, 130, 120)) + list(np.linspace(130, 110, 40))
    stock = _price_df(base)
    index = _price_df([x * 2 for x in base])   # aynı yönde, 2x ölçek
    r = compute_risk(stock, index)
    assert r.beta is not None and 0.7 < r.beta < 1.3


def _fund(**kw):
    base = dict(symbol="X", pe_trailing=None, pe_forward=None, price_to_book=None,
                profit_margin=None, operating_margin=None, return_on_equity=None,
                debt_to_equity=None, current_ratio=None, dividend_yield=None)
    base.update(kw)
    return Fundamentals(**base)


def _ev(fund):
    snap = StockSnapshot(symbol="X", name="X", market=Market.US, currency="USD",
                         price=10, previous_close=10, day_change_pct=0,
                         market_cap=1e9, sector="Tech", exchange="NMS")
    return StockEvaluation(symbol="X", snapshot=snap, fundamentals=fund)


def test_snowflake_ucuz_karli_saglam_yuksek_puan():
    f = _fund(pe_trailing=7, price_to_book=0.9, return_on_equity=0.30,
              profit_margin=0.25, operating_margin=0.28, debt_to_equity=0.2,
              current_ratio=2.0, dividend_yield=0.06)
    sf = compute_snowflake(_ev(f))
    assert sf.values["Değer"] >= 80
    assert sf.values["Kârlılık"] >= 80
    assert sf.values["Sağlık"] >= 75
    assert sf.total >= 60


def test_snowflake_veri_yoksa_none():
    sf = compute_snowflake(_ev(None))
    assert all(v is None for k, v in sf.values.items() if k != "Temettü")
