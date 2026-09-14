"""
Temettü + bilanço takvimi (yfinance).

ABD hisselerinde dolu; BIST'te temettü tarihleri sık sık eksik/eski.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

log = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    symbol: str
    name: str
    kind: str            # "earnings" | "dividend"
    event_date: date
    detail: str = ""

    @property
    def days_away(self) -> int:
        return (self.event_date - date.today()).days


def _as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, (list, tuple)) and v:
        return _as_date(v[0])
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except ValueError:
        return None


class CalendarProvider:
    def upcoming(self, symbols: list[str], *, past_days: int = 3) -> list[CalendarEvent]:
        """Verilen sembollerin yaklaşan (ve son birkaç gün) temettü + bilanço olayları."""
        import yfinance as yf

        today = date.today()
        out: list[CalendarEvent] = []
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                cal = t.calendar or {}
                name = (t.info.get("shortName") or sym) if hasattr(t, "info") else sym
            except Exception as e:
                log.info("calendar %s hata: %s", sym, e)
                continue

            ed = _as_date(cal.get("Earnings Date"))
            if ed and (ed - today).days >= -past_days:
                avg = cal.get("Earnings Average")
                detail = f"beklenti HBK ~{avg:.2f}" if isinstance(avg, (int, float)) else ""
                out.append(CalendarEvent(sym, name, "earnings", ed, detail))

            xd = _as_date(cal.get("Ex-Dividend Date"))
            if xd and (xd - today).days >= -past_days:
                dd = _as_date(cal.get("Dividend Date"))
                detail = f"ödeme {dd:%d.%m.%Y}" if dd else ""
                out.append(CalendarEvent(sym, name, "dividend", xd, detail))

        out.sort(key=lambda e: e.event_date)
        return out
