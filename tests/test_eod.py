"""eod.py — iki kayıt arasındaki sinyal tespiti (saf, ağ yok)."""

from __future__ import annotations

from src.analysis.eod import _signals_between


def _row(**kw):
    base = dict(trend="Yatay / Karışık", rsi_14=50.0, cross_signal=None,
               price_vs_sma200_pct=5.0)
    base.update(kw)
    return base


def test_onceki_yoksa_sadece_taze_kesisim():
    out = _signals_between(_row(cross_signal="Altın kesişim (1 gün önce)"), None)
    assert out == ["Yeni Altın kesişim (1 gün önce)"]
    assert _signals_between(_row(), None) == []


def test_trend_degisimi():
    out = _signals_between(_row(trend="Yükseliş"), _row(trend="Düşüş"))
    assert any("Trend değişti: Düşüş → Yükseliş" in s for s in out)


def test_rsi_asiri_bolgeye_giris():
    out = _signals_between(_row(rsi_14=75), _row(rsi_14=55))
    assert any("aşırı alım bölgesine girdi" in s for s in out)


def test_sma200_taraf_degisimi():
    yukari = _signals_between(_row(price_vs_sma200_pct=3), _row(price_vs_sma200_pct=-4))
    assert "Fiyat SMA200'ün üstüne çıktı" in yukari
    asagi = _signals_between(_row(price_vs_sma200_pct=-2), _row(price_vs_sma200_pct=6))
    assert "Fiyat SMA200'ün altına indi" in asagi


def test_eski_kesisim_taze_sayilmaz():
    out = _signals_between(_row(cross_signal="Altın kesişim (30 gün önce)"), _row())
    assert not any("Yeni" in s for s in out)
