"""
Mali tablo geçmişi sağlayıcısı (Bilanço Karnesi).

BIST  -> İş Yatırım MaliTablo (çok yıl)
ABD   -> yfinance yıllık gelir tablosu / bilanço / nakit akışı

Çıktı: FinancialHistory (eski -> yeni sıralı FinancialPeriod listesi).
Kaynak yoksa/hata olursa ProviderError.
"""

from __future__ import annotations

import logging
from datetime import date

from src.models import FinancialHistory, FinancialPeriod
from src.providers.base import ProviderError
from src.providers.isyatirim_provider import bist_code, fetch_maltablo, is_bist_symbol

log = logging.getLogger(__name__)

# İş Yatırım MaliTablo kalem kodları
_REVENUE = "3C"
_GROSS = "3D"
_OPERATING = "3DF"
_NET = "3Z"
_DEP = "4B"          # amortisman (FAVÖK için)
_EQUITY = "2O"       # ana ortaklığa ait özkaynak
_TOTAL_EQUITY = "2N"  # azınlık dahil (borç hesabı için)
_TOTAL_ASSETS = "1BL"
_CUR_ASSETS = "1A"
_CUR_LIAB = "2A"
_OCF = "4CAG"        # esas faaliyetten nakit
_OCF_ALT = "4C"


class StatementsProvider:
    def get_history(self, symbol: str, years: int = 4) -> FinancialHistory:
        symbol = symbol.strip().upper()
        if is_bist_symbol(symbol):
            return self._bist_history(symbol, years)
        return self._us_history(symbol, years)

    # ---- BIST ------------------------------------------------------

    def _bist_history(self, symbol: str, years: int) -> FinancialHistory:
        code = bist_code(symbol)
        this_year = date.today().year
        by_year: dict[int, dict[int, dict[str, float]]] = {}
        for y in range(this_year, this_year - years - 1, -1):
            try:
                data = fetch_maltablo(code, y)
            except ProviderError:
                data = {}
            if data:
                by_year[y] = data

        if not by_year:
            raise ProviderError(f"{code}: İş Yatırım mali tablo geçmişi bulunamadı.")

        periods: list[FinancialPeriod] = []

        # Tam yıllar (period 12) — eskiden yeniye
        for y in sorted(by_year):
            d12 = by_year[y].get(12)
            if d12 and d12.get(_EQUITY) is not None:
                periods.append(self._bist_period(y, 12, d12, annual=True))

        # En güncel yılın ara dönemi (varsa ve 12 değilse — tazelik için)
        latest_y = max(by_year)
        for p in (9, 6, 3):
            dp = by_year[latest_y].get(p)
            if dp and dp.get(_EQUITY) is not None:
                periods.append(self._bist_period(latest_y, p, dp, annual=False))
                break

        if not periods:
            raise ProviderError(f"{code}: XI_29 formatına uymuyor (banka olabilir).")

        return FinancialHistory(
            symbol=symbol, currency="TRY", source="İş Yatırım", periods=periods,
        )

    @staticmethod
    def _bist_period(year: int, period: int, d: dict[str, float], *, annual: bool) -> FinancialPeriod:
        def g(code: str) -> float | None:
            return d.get(code)

        op = g(_OPERATING)
        dep = g(_DEP)
        ebitda = op + dep if (op is not None and dep is not None) else None

        total_assets = g(_TOTAL_ASSETS)
        total_equity = g(_TOTAL_EQUITY)
        total_debt = (
            total_assets - total_equity
            if (total_assets is not None and total_equity is not None)
            else None
        )

        label = f"{year}/{period}" + ("" if annual else f" ({period} ay)")
        return FinancialPeriod(
            label=label, year=year, period=period, is_annual=annual,
            revenue=g(_REVENUE), gross_profit=g(_GROSS), operating_profit=op,
            ebitda=ebitda, net_income=g(_NET),
            equity=g(_EQUITY), total_assets=total_assets, total_debt=total_debt,
            current_assets=g(_CUR_ASSETS), current_liabilities=g(_CUR_LIAB),
            operating_cash_flow=g(_OCF) if g(_OCF) is not None else g(_OCF_ALT),
        )

    # ---- ABD (yfinance) -----------------------------------------

    def _us_history(self, symbol: str, years: int) -> FinancialHistory:
        import yfinance as yf

        t = yf.Ticker(symbol)
        try:
            inc = t.income_stmt
            bal = t.balance_sheet
            cf = t.cashflow
        except Exception as e:
            raise ProviderError(f"{symbol}: yfinance mali tablo alınamadı: {e}") from e

        if inc is None or inc.empty:
            raise ProviderError(f"{symbol}: mali tablo verisi yok.")

        def row(df, *names):
            if df is None or df.empty:
                return {}
            for n in names:
                if n in df.index:
                    return df.loc[n].to_dict()
            return {}

        rev = row(inc, "Total Revenue", "TotalRevenue")
        gross = row(inc, "Gross Profit")
        opinc = row(inc, "Operating Income", "OperatingIncome")
        ebitda = row(inc, "EBITDA", "Normalized EBITDA")
        net = row(inc, "Net Income", "Net Income Common Stockholders")
        eq = row(bal, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest")
        ta = row(bal, "Total Assets")
        td = row(bal, "Total Debt", "Net Debt")
        ca = row(bal, "Current Assets", "Total Current Assets")
        cl = row(bal, "Current Liabilities", "Total Current Liabilities")
        ocf = row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")

        cols = sorted(inc.columns)[-(years):]   # eskiden yeniye
        periods: list[FinancialPeriod] = []
        for c in cols:
            def gv(m):
                v = m.get(c)
                try:
                    v = float(v)
                    return None if v != v else v
                except (TypeError, ValueError):
                    return None
            periods.append(FinancialPeriod(
                label=str(c.year) if hasattr(c, "year") else str(c),
                year=c.year if hasattr(c, "year") else 0,
                period=12, is_annual=True,
                revenue=gv(rev), gross_profit=gv(gross), operating_profit=gv(opinc),
                ebitda=gv(ebitda), net_income=gv(net),
                equity=gv(eq), total_assets=gv(ta), total_debt=gv(td),
                current_assets=gv(ca), current_liabilities=gv(cl),
                operating_cash_flow=gv(ocf),
            ))

        if not periods:
            raise ProviderError(f"{symbol}: mali tablo dönemleri çıkarılamadı.")

        cur = None
        try:
            cur = t.fast_info.get("currency")
        except Exception:
            pass
        return FinancialHistory(
            symbol=symbol, currency=cur, source="yfinance", periods=periods,
        )
