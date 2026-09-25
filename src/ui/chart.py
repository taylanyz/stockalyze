"""
Fiyat grafikleri (Plotly) — fiyat + hareketli ortalamalar, hacim, RSI.

Streamlit'e özgü sunum. Hesaplama analysis/technical'dan geliyor.
Göstergeler HER ZAMAN tam geçmişten hesaplanır; sadece görünen pencere daraltılır
(1 aylık görünümde bile SMA200 doğru).

Üç ayrı, küçük grafik döner (tek büyük mega-grafik yerine): fiyat grafiği tam
genişlikte üstte, hacim + RSI altında yan yana — sayfa daha az yer kaplasın.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.analysis.technical import (
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    SMA_LONG,
    SMA_SHORT,
    rsi_wilder,
    simple_moving_average,
)

_COMMON_LAYOUT = dict(
    margin=dict(l=10, r=10, t=34, b=10),
    dragmode=False,           # sürükleyerek kaydırma kapalı
    hovermode="x",
)


def _lock_and_window(fig: go.Figure, view_days: int | None, df: pd.DataFrame) -> None:
    if view_days and len(df) > 2:
        end = df.index[-1]
        start = end - pd.Timedelta(days=view_days)
        fig.update_xaxes(range=[start, end])
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)


def price_line_chart(
    df: pd.DataFrame, title: str, view_days: int | None = None,
) -> go.Figure:
    """Kapanış fiyatı (alan/çizgi) + SMA50 + SMA200. Tam genişlik, orta yükseklik."""
    close = df["Close"]
    sma_s = simple_moving_average(close, SMA_SHORT)
    sma_l = simple_moving_average(close, SMA_LONG)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=close, name="Fiyat", mode="lines",
        line=dict(width=1.8, color="#4c8bf5"),
        fill="tozeroy", fillcolor="rgba(76, 139, 245, 0.12)",
        hoverinfo="x+y",
    ))
    fig.add_trace(go.Scatter(x=df.index, y=sma_s, name=f"SMA {SMA_SHORT}",
                             line=dict(width=1.2, color="#f0a202")))
    fig.add_trace(go.Scatter(x=df.index, y=sma_l, name=f"SMA {SMA_LONG}",
                             line=dict(width=1.2, color="#26a69a")))

    if view_days and len(df) > 2:
        end = df.index[-1]
        start = end - pd.Timedelta(days=view_days)
        vis_mask = df.index >= start
        candidates = pd.concat([close[vis_mask], sma_s[vis_mask], sma_l[vis_mask]]).dropna()
        if len(candidates):
            lo, hi = float(candidates.min()), float(candidates.max())
            pad = (hi - lo) * 0.06 or hi * 0.02
            fig.update_yaxes(range=[lo - pad, hi + pad])

    fig.update_layout(
        title=dict(text=title or "Fiyat", x=0.01, font=dict(size=13)),
        height=300, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        xaxis_rangeslider_visible=False,
        **_COMMON_LAYOUT,
    )
    _lock_and_window(fig, view_days, df)
    return fig


def spectrum_gauge(
    value: float | None, axis_range: tuple[float, float],
    zones: list[tuple[float, str]], title: str,
) -> go.Figure:
    """
    Bir değerin bir aralıkta NEREDE durduğunu gösteren ibre grafiği — sayı
    okumaya gerek kalmadan "ucuz mu pahalı mı" gibi soruların görsel cevabı.

    zones: [(üst_sınır, renk), ...] artan sırada; son bölge axis_range[1]'e
    kadar sürer. value None ise ibre aralığın altına sabitlenir + "veri yok"
    görünümü UI tarafında ayrıca ele alınmalı.
    """
    lo, hi = axis_range
    v = value if value is not None else lo
    v = max(lo, min(hi, v))   # ibre aralık dışına taşmasın

    steps = []
    start = lo
    for upper, color in zones:
        end = min(upper, hi)
        if end > start:
            steps.append(dict(range=[start, end], color=color))
        start = end
        if start >= hi:
            break

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=v,
        number=dict(font=dict(size=22)),
        title=dict(text=title, font=dict(size=13)),
        gauge=dict(
            axis=dict(range=[lo, hi], tickfont=dict(size=9)),
            bar=dict(color="rgba(26,26,46,0.75)", thickness=0.28),
            bgcolor="rgba(0,0,0,0)",
            steps=steps,
            threshold=dict(line=dict(color="rgba(26,26,46,0.9)", width=3),
                           thickness=0.85, value=v),
        ),
    ))
    fig.update_layout(height=170, margin=dict(l=25, r=25, t=45, b=10))
    return fig


def volume_chart(df: pd.DataFrame, view_days: int | None = None) -> go.Figure:
    """Günlük işlem hacmi (bar). Yarı genişlik, kısa."""
    close = df["Close"]
    vol_colors = ["#26a69a" if c >= o else "#ef5350"
                  for o, c in zip(df["Open"], close)]
    fig = go.Figure(go.Bar(x=df.index, y=df["Volume"], name="Hacim",
                           marker_color=vol_colors, showlegend=False))

    if view_days and len(df) > 2:
        end = df.index[-1]
        start = end - pd.Timedelta(days=view_days)
        vis = df[df.index >= start]
        if len(vis):
            fig.update_yaxes(range=[0, float(vis["Volume"].max()) * 1.15])

    fig.update_layout(
        title=dict(text="Hacim", x=0.01, font=dict(size=13)),
        height=230, showlegend=False,
        **_COMMON_LAYOUT,
    )
    _lock_and_window(fig, view_days, df)
    return fig


def rsi_chart(df: pd.DataFrame, view_days: int | None = None) -> go.Figure:
    """RSI (14) — aşırı alım/satım eşikleriyle. Yarı genişlik, kısa."""
    rsi = rsi_wilder(df["Close"])
    fig = go.Figure(go.Scatter(x=df.index, y=rsi, name="RSI",
                               line=dict(width=1.2, color="#ab47bc"),
                               showlegend=False))
    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dot", line_color="#ef5350", line_width=1)
    fig.add_hline(y=RSI_OVERSOLD, line_dash="dot", line_color="#26a69a", line_width=1)

    fig.update_layout(
        title=dict(text="RSI (14)", x=0.01, font=dict(size=13)),
        height=230, showlegend=False,
        yaxis=dict(range=[0, 100]),
        **_COMMON_LAYOUT,
    )
    _lock_and_window(fig, view_days, df)
    return fig
