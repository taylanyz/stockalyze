"""
Risk metrikleri — fiyat geçmişinden hesaplanır. Saf fonksiyonlar, ağ yok.

  - Yıllık volatilite: günlük getirilerin std'si × √252 (ne kadar oynak)
  - Beta: hissenin endeksle birlikte hareket katsayısı (kovaryans / endeks varyansı)
  - Maksimum düşüş: son dönemde en tepeden en dibe en büyük % kayıp
  - Endekse relatif getiri: aynı dönemde hisse getirisi − endeks getirisi

Tahmin değil, tarif: "bu hisse ne kadar oynak / endeksle ne kadar bağlı".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


@dataclass
class RiskMetrics:
    volatility_annual: float | None       # kesir (0.35 = %35)
    beta: float | None
    max_drawdown: float | None            # kesir, negatif (−0.28 = %-28)
    return_pct: float | None              # dönem getirisi (kesir)
    index_return_pct: float | None
    relative_return_pct: float | None     # hisse − endeks

    @property
    def level(self) -> str:
        v = self.volatility_annual
        if v is None:
            return "belirsiz"
        if v < 0.25:
            return "düşük"
        if v < 0.45:
            return "orta"
        return "yüksek"


def _daily_returns(closes: pd.Series) -> pd.Series:
    return closes.pct_change().dropna()


def _max_drawdown(closes: pd.Series) -> float | None:
    if len(closes) < 2:
        return None
    running_max = closes.cummax()
    dd = closes / running_max - 1.0
    return float(dd.min())


def compute_risk(
    price_df: pd.DataFrame, index_df: pd.DataFrame | None = None
) -> RiskMetrics:
    """
    price_df: hissenin OHLCV geçmişi (Close sütunu).
    index_df: aynı dönem endeks geçmişi (beta + relatif getiri için); yoksa None.
    """
    closes = price_df["Close"].dropna()
    if len(closes) < 30:
        return RiskMetrics(None, None, None, None, None, None)

    rets = _daily_returns(closes)
    vol = float(rets.std() * np.sqrt(_TRADING_DAYS)) if len(rets) > 5 else None
    mdd = _max_drawdown(closes)
    ret = float(closes.iloc[-1] / closes.iloc[0] - 1.0)

    beta = idx_ret = rel = None
    if index_df is not None and not index_df.empty:
        idx_closes = index_df["Close"].dropna()
        # ortak tarihlerde hizala
        joined = pd.concat([closes, idx_closes], axis=1, join="inner").dropna()
        joined.columns = ["s", "i"]
        if len(joined) >= 30:
            sr = joined["s"].pct_change().dropna()
            ir = joined["i"].pct_change().dropna()
            common = pd.concat([sr, ir], axis=1, join="inner").dropna()
            common.columns = ["s", "i"]
            if len(common) >= 20 and common["i"].var() > 0:
                beta = float(common["s"].cov(common["i"]) / common["i"].var())
            idx_ret = float(joined["i"].iloc[-1] / joined["i"].iloc[0] - 1.0)
            rel = ret - idx_ret

    return RiskMetrics(
        volatility_annual=vol, beta=beta, max_drawdown=mdd,
        return_pct=ret, index_return_pct=idx_ret, relative_return_pct=rel,
    )


def describe_risk(r: RiskMetrics) -> list[str]:
    """Kısa maddeler."""
    out: list[str] = []
    if r.volatility_annual is not None:
        out.append(
            f"Yıllık volatilite %{r.volatility_annual * 100:.0f} ({r.level} oynaklık)."
        )
    if r.beta is not None:
        rel = ("endeksten daha oynak" if r.beta > 1.15
               else "endeksten daha sakin" if r.beta < 0.85 else "endeksle benzer")
        out.append(f"Beta {r.beta:.2f} — {rel}.")
    if r.max_drawdown is not None:
        out.append(f"Son 2 yılda en büyük düşüş %{r.max_drawdown * 100:.0f}.")
    if r.relative_return_pct is not None:
        yon = "önde" if r.relative_return_pct > 0 else "geride"
        out.append(
            f"Endekse göre %{r.relative_return_pct * 100:+.0f} {yon} "
            f"(hisse %{r.return_pct * 100:+.0f}, endeks %{r.index_return_pct * 100:+.0f})."
        )
    return out or ["Risk metriği için yeterli fiyat geçmişi yok."]
