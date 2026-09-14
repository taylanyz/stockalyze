"""
Teknik göstergeler.

Buradaki fonksiyonlar SAF: girdi bir pandas DataFrame (OHLCV),
çıktı sayılar / TechnicalIndicators. Ağ yok, dosya yok, print yok.
Bu yüzden test etmesi kolay ve tekrar kullanılabilir.

Göstergeler ve ne işe yaradıkları:
  - SMA (Simple Moving Average / basit hareketli ortalama):
    Son N günün kapanış ortalaması. Fiyat SMA'nın üstündeyse
    kısa vadeli yön yukarı kabul edilir.
  - Altın/Ölüm kesişimi: SMA50'nin SMA200'ü yukarı kesmesi (altın,
    boğa sinyali) veya aşağı kesmesi (ölüm, ayı sinyali).
  - RSI (Relative Strength Index): 0-100 arası momentum göstergesi.
    >70 "aşırı alım" (fiyat hızlı yükselmiş, düzeltme gelebilir),
    <30 "aşırı satım". Wilder'ın orijinal yumuşatma yöntemiyle.
  - Hacim trendi: son günün işlem hacmi / son 20 günün ortalaması.
    >1 ise ortalamanın üstünde ilgi var demektir.
"""

from __future__ import annotations

import pandas as pd

from src.models import RSIZone, TechnicalIndicators, Trend

# Ayarlanabilir sabitler — tek yerde dursun.
SMA_SHORT = 50
SMA_LONG = 200
RSI_PERIOD = 14
VOLUME_WINDOW = 20
CROSS_LOOKBACK = 60          # kesişimi kaç gün geriye kadar arayalım
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0


def simple_moving_average(closes: pd.Series, window: int) -> pd.Series:
    """Son `window` günün kapanış ortalaması (kayan pencere)."""
    return closes.rolling(window=window).mean()


def price_with_smas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Grafik için: Kapanış + SMA50 + SMA200 sütunlu DataFrame.
    (Streamlit fiyat grafiği bunu doğrudan çizer.)
    """
    closes = df["Close"]
    return pd.DataFrame({
        "Fiyat": closes,
        f"SMA {SMA_SHORT}": simple_moving_average(closes, SMA_SHORT),
        f"SMA {SMA_LONG}": simple_moving_average(closes, SMA_LONG),
    })


def rsi_wilder(closes: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    Wilder yöntemiyle RSI.

    Adımlar:
      1. Günlük fiyat farkı (delta).
      2. Kazançlar (delta>0) ve kayıplar (delta<0) ayrı serilere.
      3. Her ikisinin de üstel yumuşatılmış ortalaması (alpha = 1/period).
      4. RS = ortalama kazanç / ortalama kayıp
      5. RSI = 100 - 100 / (1 + RS)
    """
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # avg_loss == 0 durumunda rs = sonsuz -> rsi = 100 (doğru davranış).
    return rsi


def _detect_cross(sma_short: pd.Series, sma_long: pd.Series) -> str | None:
    """
    Son CROSS_LOOKBACK gün içinde SMA50 ile SMA200 kesişti mi?

    (sma_short - sma_long) işaretinin en son ne zaman değiştiğine bakarız.
    - negatiften pozitife  -> Altın kesişim
    - pozitiften negatife   -> Ölüm kesişimi
    """
    diff = (sma_short - sma_long).dropna()
    if len(diff) < 2:
        return None

    window = diff.tail(CROSS_LOOKBACK)
    sign = window.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

    # Son satırdan geriye doğru git, işaret değişimini bul.
    values = sign.tolist()
    for i in range(len(values) - 1, 0, -1):
        prev, curr = values[i - 1], values[i]
        if prev < 0 and curr > 0:
            days_ago = len(values) - 1 - i
            return f"Altın kesişim ({days_ago} gün önce)"
        if prev > 0 and curr < 0:
            days_ago = len(values) - 1 - i
            return f"Ölüm kesişimi ({days_ago} gün önce)"
    return None


def _classify_trend(
    price: float | None, sma_s: float | None, sma_l: float | None
) -> Trend:
    """Fiyat ve iki ortalamanın dizilişine göre trend etiketi."""
    if price is None or sma_s is None:
        return Trend.UNKNOWN
    if sma_l is None:
        # Sadece kısa ortalama var: kaba bir tahmin.
        return Trend.UP if price > sma_s else Trend.DOWN
    if price > sma_s > sma_l:
        return Trend.UP
    if price < sma_s < sma_l:
        return Trend.DOWN
    return Trend.SIDEWAYS


_TRADING_DAYS_PER_MONTH = 21
_PRIOR_WINDOW = 40   # trend başlamadan önceki dönemi ölçmek için gün sayısı


def _daily_trend_series(df: pd.DataFrame) -> list[Trend]:
    """Her gün için trend sınıflandırması (vektörel, hızlı)."""
    closes = df["Close"]
    s50 = simple_moving_average(closes, SMA_SHORT)
    s200 = simple_moving_average(closes, SMA_LONG)
    out: list[Trend] = []
    for c, a, b in zip(closes.tolist(), s50.tolist(), s200.tolist()):
        if a != a:  # NaN
            out.append(Trend.UNKNOWN)
        elif b != b:
            out.append(Trend.UP if c > a else Trend.DOWN)
        elif c > a > b:
            out.append(Trend.UP)
        elif c < a < b:
            out.append(Trend.DOWN)
        else:
            out.append(Trend.SIDEWAYS)
    return out


def _trend_context(
    df: pd.DataFrame, current: Trend
) -> tuple[int | None, Trend | None, float | None]:
    """
    (trend_yaşı_gün, önceki_trend, önceki_dönem_getirisi_%)

    trend_yaşı: fiyatın kesintisiz kaç gündür 200 günlük ortalamanın AYNI
      tarafında olduğu. (Tam üçlü diziliş çok sık kırıldığı için 'yaş' ölçüsü
      olarak fiyat–SMA200 tarafını kullanıyoruz; daha kararlı.)
    önceki_trend: bu dönem başlamadan önceki ~30 günün baskın sınıflandırması.
    önceki_getiri: dönem başlamadan önceki ~40 günde fiyat % değişimi.
    """
    if current is Trend.UNKNOWN or len(df) < 3:
        return None, None, None

    closes = df["Close"]
    sma200 = simple_moving_average(closes, SMA_LONG)
    diff = (closes - sma200).dropna()
    if len(diff) < 5:
        return None, None, None

    signs = [1 if d > 0 else -1 for d in diff.tolist()]
    today = signs[-1]
    age = 0
    for s in reversed(signs):
        if s == today:
            age += 1
        else:
            break
    if age >= len(signs):
        return age, None, None   # fiyat tüm (SMA200'lü) geçmiş boyunca aynı tarafta

    # Serinin başladığı indeksi tam DataFrame'e göre bul.
    offset = len(df) - len(signs)      # baştaki NaN (SMA200 ısınma) sayısı
    start = offset + len(signs) - age

    series = _daily_trend_series(df)

    # Önceki trend: dönüşün hemen öncesi genelde 'yatay' (200-ort. etrafında
    # salınım) olduğundan, geçiş bölgesini atlayıp ~50–15 gün öncesine bakıyoruz.
    lookback = [
        t for t in series[max(0, start - 50):max(0, start - 15)]
        if t is not Trend.UNKNOWN
    ]
    prior_trend = max(set(lookback), key=lookback.count) if lookback else None

    lo = max(0, start - 1 - _PRIOR_WINDOW)
    p0, p1 = float(closes.iloc[lo]), float(closes.iloc[start - 1])
    prior_ret = (p1 - p0) / p0 * 100 if p0 else None
    return age, prior_trend, prior_ret


def describe_trend(tech: TechnicalIndicators) -> list[str]:
    """
    Trend sınıflandırmasının gerekçesini KISA MADDELER halinde döndürür.
    Her madde alt alta gösterilir (Radar detay paneli + CLI).
    """
    if tech.last_close is None or tech.sma_50 is None:
        return ["Yeterli fiyat geçmişi yok (SMA50 için ~50, SMA200 için "
                "~200 işlem günü gerekir)."]

    lines: list[str] = []

    dizilis = {
        Trend.UP: "fiyat her iki hareketli ortalamanın da ÜZERİNDE (yükseliş dizilişi)",
        Trend.DOWN: "fiyat her iki hareketli ortalamanın da ALTINDA (düşüş dizilişi)",
        Trend.SIDEWAYS: "fiyat ortalamaların arasında — net yükseliş/düşüş sıralaması yok",
    }.get(tech.trend, "yeterli veri yok")
    lines.append(f"Diziliş: {dizilis}.")

    if tech.price_vs_sma200_pct is not None:
        lines.append(
            f"200 günlük ortalamaya uzaklık: %{tech.price_vs_sma200_pct:+.1f}."
        )

    # --- trendin yaşı ve öncesi (tahmin değil, tarif) --------------
    if tech.trend_age_days:
        months = tech.trend_age_days / _TRADING_DAYS_PER_MONTH
        dur = f"~{tech.trend_age_days} işlem günü"
        if months >= 1.5:
            dur += f" (~{months:.0f} ay)"
        age = f"Trendin yaşı: {dur}"
        if tech.trend_age_days <= 10:
            age += " — taze, henüz teyitsiz"
        lines.append(age + ".")
        if tech.prior_trend is not None:
            was = {
                "Yükseliş": "yükseliş trendindeydi", "Düşüş": "düşüş trendindeydi",
                "Yatay / Karışık": "yatay seyrediyordu",
            }.get(tech.prior_trend.value, "belirsizdi")
            prev = f"Öncesinde {was}"
            if tech.prior_return_pct is not None:
                prev += f" (dönüş öncesi fiyat %{tech.prior_return_pct:+.0f})"
            lines.append(prev + ".")

    if tech.cross_signal:
        lines.append(f"Kesişim: {tech.cross_signal}.")

    if tech.rsi_14 is not None:
        lines.append(f"RSI: {tech.rsi_14:.0f} ({tech.rsi_zone.value.lower()}).")

    if tech.volume_ratio is not None:
        lines.append(
            f"Hacim: son gün, 20 günlük ortalamanın {tech.volume_ratio:.2f} katı."
        )

    return lines


def _classify_rsi(rsi: float | None) -> RSIZone:
    if rsi is None or pd.isna(rsi):
        return RSIZone.UNKNOWN
    if rsi >= RSI_OVERBOUGHT:
        return RSIZone.OVERBOUGHT
    if rsi <= RSI_OVERSOLD:
        return RSIZone.OVERSOLD
    return RSIZone.NEUTRAL


def _last_valid(series: pd.Series) -> float | None:
    """Serinin son geçerli (NaN olmayan) değeri; yoksa None."""
    s = series.dropna()
    return float(s.iloc[-1]) if not s.empty else None


def compute_technical(symbol: str, df: pd.DataFrame) -> TechnicalIndicators:
    """
    OHLCV DataFrame'inden tüm teknik göstergeleri hesapla.

    df: provider.get_price_history() çıktısı — Open/High/Low/Close/Volume.
    """
    closes = df["Close"]
    volumes = df["Volume"]

    sma50_series = simple_moving_average(closes, SMA_SHORT)
    sma200_series = simple_moving_average(closes, SMA_LONG)
    rsi_series = rsi_wilder(closes, RSI_PERIOD)

    last_close = _last_valid(closes)
    sma_50 = _last_valid(sma50_series)
    sma_200 = _last_valid(sma200_series)
    rsi_14 = _last_valid(rsi_series)

    price_vs_sma50 = (
        (last_close - sma_50) / sma_50 * 100
        if last_close is not None and sma_50
        else None
    )
    price_vs_sma200 = (
        (last_close - sma_200) / sma_200 * 100
        if last_close is not None and sma_200
        else None
    )

    volume_last = _last_valid(volumes)
    vol_avg_series = volumes.rolling(window=VOLUME_WINDOW).mean()
    volume_avg_20 = _last_valid(vol_avg_series)
    volume_ratio = (
        volume_last / volume_avg_20
        if volume_last is not None and volume_avg_20
        else None
    )

    trend = _classify_trend(last_close, sma_50, sma_200)
    trend_age, prior_trend, prior_ret = _trend_context(df, trend)

    return TechnicalIndicators(
        symbol=symbol,
        as_of=df.index[-1].strftime("%Y-%m-%d") if len(df) else "N/A",
        data_points=len(df),
        last_close=last_close,
        sma_50=sma_50,
        sma_200=sma_200,
        price_vs_sma50_pct=price_vs_sma50,
        price_vs_sma200_pct=price_vs_sma200,
        trend=trend,
        cross_signal=_detect_cross(sma50_series, sma200_series),
        rsi_14=rsi_14,
        rsi_zone=_classify_rsi(rsi_14),
        volume_last=volume_last,
        volume_avg_20=volume_avg_20,
        volume_ratio=volume_ratio,
        trend_age_days=trend_age,
        prior_trend=prior_trend,
        prior_return_pct=prior_ret,
    )
