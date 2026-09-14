"""
Gelişmiş fiyat grafiği (Plotly) — mum + hareketli ortalamalar + hacim + RSI.

Streamlit'e özgü sunum. Hesaplama analysis/technical'dan geliyor.
Göstergeler HER ZAMAN tam geçmişten hesaplanır; sadece görünen pencere daraltılır
(1 aylık görünümde bile SMA200 doğru).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.technical import (
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    SMA_LONG,
    SMA_SHORT,
    rsi_wilder,
    simple_moving_average,
)


def price_chart(
    df: pd.DataFrame,
    title: str = "Fiyat / Hacim / RSI",
    view_days: int | None = None,
) -> go.Figure:
    """
    df: OHLCV (tarih indeksli) — TAM geçmiş.
    view_days: yalnızca son N günü göster (göstergeler yine tam geçmişten).
    """
    close = df["Close"]
    sma_s = simple_moving_average(close, SMA_SHORT)
    sma_l = simple_moving_average(close, SMA_LONG)
    rsi = rsi_wilder(close)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.62, 0.16, 0.22], vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=close,
        name="Fiyat", showlegend=False, hoverinfo="x+y",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma_s, name=f"SMA {SMA_SHORT}",
                             line=dict(width=1.2, color="#f0a202")), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma_l, name=f"SMA {SMA_LONG}",
                             line=dict(width=1.2, color="#4c8bf5")), row=1, col=1)

    vol_colors = ["#26a69a" if c >= o else "#ef5350"
                  for o, c in zip(df["Open"], close)]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Hacim",
                         marker_color=vol_colors, showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                             line=dict(width=1.2, color="#ab47bc"),
                             showlegend=False), row=3, col=1)
    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dot", line_color="#ef5350",
                  line_width=1, row=3, col=1)
    fig.add_hline(y=RSI_OVERSOLD, line_dash="dot", line_color="#26a69a",
                  line_width=1, row=3, col=1)

    # --- görünen pencere ---
    if view_days and len(df) > 2:
        end = df.index[-1]
        start = end - pd.Timedelta(days=view_days)
        fig.update_xaxes(range=[start, end])
        vis = df[df.index >= start]
        if len(vis) >= 2:
            lo, hi = float(vis["Low"].min()), float(vis["High"].max())
            pad = (hi - lo) * 0.06 or hi * 0.02
            fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)
            fig.update_yaxes(range=[0, float(vis["Volume"].max()) * 1.15], row=2, col=1)

    fig.update_layout(
        title=dict(text=title or "Fiyat", x=0.01, font=dict(size=13)),
        height=560, margin=dict(l=10, r=10, t=34, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
        hovermode="x",
        dragmode=False,          # sürükleyerek kaydırma kapalı
    )
    # her eksende zoom/pan kilitli — grafik kendi bölgesinde kalır
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    fig.update_yaxes(title_text="Hacim", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
    return fig
