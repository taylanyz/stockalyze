"""
Metrik değerlerini basit 🟢/🟡/🔴 rozetine çeviren yardımcılar.

Amaç: F/K = 12.3 gibi çıplak bir sayı gördüğünde "bu iyi mi kötü mü"
sorusuna anında bir ipucu vermek. Eşikler src/analysis/scoring.py'deki
puanlama bantlarıyla tutarlı tutulur; burada sadece görüntüleme için
üç seviyeye indirgenir.

Yatırım tavsiyesi değildir — sadece okumayı kolaylaştırır.
"""

from __future__ import annotations

from src.models import Market

_NA = ("⚪", "veri yok")

# "olumlu"/"temkinli"/"riskli"/"notr" etiketli metinler için ortak ikon eşlemesi
# (Radar konumlanma notu + Bilanço Karnesi yorumları aynı sözlüğü paylaşır).
TAG_ICON = {"olumlu": "🟢", "temkinli": "🟡", "riskli": "🔴", "notr": "⚪"}


def badge_pe(value: float | None, market: Market) -> tuple[str, str]:
    if value is None or value <= 0:
        return "⚪", "kâr yok / veri yok"
    e1, e2, e3 = (6, 10, 15) if market == Market.BIST else (15, 25, 40)
    if value <= e1:
        return "🟢", "ucuz"
    if value <= e2:
        return "🟡", "orta"
    if value <= e3:
        return "🟡", "orta-yüksek"
    return "🔴", "pahalı"


def badge_pb(value: float | None, market: Market) -> tuple[str, str]:
    if value is None:
        return _NA
    e1, e2 = (1.5, 3) if market == Market.BIST else (3, 6)
    if value <= e1:
        return "🟢", "düşük"
    if value <= e2:
        return "🟡", "orta"
    return "🔴", "yüksek"


# --- ibre grafiği (gauge) ayarları — badge_* ile AYNI eşikler, sadece
# aralık + pastel renk bandına çevrilmiş hali (src/ui/chart.py::spectrum_gauge) ---

_G = "#b7e4c7"   # yeşil bant (ucuz/düşük/sağlıklı)
_Y = "#ffe8a3"   # sarı bant (orta)
_R = "#f5b7b1"   # kırmızı bant (pahalı/yüksek)


def gauge_pe(market: Market) -> tuple[tuple[float, float], list[tuple[float, str]]]:
    e1, e2, e3 = (6, 10, 15) if market == Market.BIST else (15, 25, 40)
    hi = e3 * 1.3
    return (0, hi), [(e1, _G), (e2, _Y), (e3, _Y), (hi, _R)]


def gauge_pb(market: Market) -> tuple[tuple[float, float], list[tuple[float, str]]]:
    e1, e2 = (1.5, 3) if market == Market.BIST else (3, 6)
    hi = e2 * 1.7
    return (0, hi), [(e1, _G), (e2, _Y), (hi, _R)]


def gauge_rsi() -> tuple[tuple[float, float], list[tuple[float, str]]]:
    return (0, 100), [(30, _Y), (70, _G), (100, _R)]


def badge_margin(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value < 0:
        return "🔴", "zarar"
    if value > 0.20:
        return "🟢", "güçlü"
    if value > 0.10:
        return "🟡", "orta"
    return "🟡", "düşük"


def badge_roe(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value < 0:
        return "🔴", "zarar"
    if value > 0.20:
        return "🟢", "güçlü"
    if value > 0.10:
        return "🟡", "orta"
    return "🟡", "zayıf"


def badge_debt_equity(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value < 1:
        return "🟢", "düşük kaldıraç"
    if value <= 2:
        return "🟡", "orta"
    return "🔴", "yüksek kaldıraç"


def badge_current_ratio(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value >= 1.5:
        return "🟢", "rahat"
    if value >= 1:
        return "🟡", "sınırda"
    return "🔴", "dar"


def badge_dividend(value: float | None) -> tuple[str, str]:
    if not value:
        return "⚪", "yok"
    if value >= 0.05:
        return "🟢", "yüksek getiri"
    return "🟡", "var"


def badge_rsi(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value >= 70:
        return "🔴", "aşırı alım"
    if value <= 30:
        return "🟡", "aşırı satım"
    if 40 <= value <= 60:
        return "🟢", "sağlıklı"
    return "🟡", "nötr"


def badge_volume(value: float | None) -> tuple[str, str]:
    if value is None:
        return _NA
    if value > 1.5:
        return "🟢", "yüksek ilgi"
    if value < 0.5:
        return "🔴", "zayıf ilgi"
    return "🟡", "normal"


def badge_cross(signal: str | None) -> tuple[str, str]:
    if not signal:
        return "⚪", "yok"
    if "Altın" in signal:
        return "🟢", "yükseliş sinyali"
    if "Ölüm" in signal:
        return "🔴", "düşüş sinyali"
    return "⚪", signal


# --- İstikrar Profili — ne kadar oynak, ne kadar kalıcı, bilanço ne kadar sağlam ---
# NOT: bunlar "iyi hisse" demek değildir; sadece davranışın ne kadar ÖNGÖRÜLEBİLİR
# olduğunu tarif eder. Kalıcı bir düşüş trendi de "istikrarlı"dır — yönü metinde ayrıca belirtilir.

def badge_volatility(level: str | None) -> tuple[str, str]:
    return {
        "düşük": ("🟢", "düşük oynaklık"),
        "orta": ("🟡", "orta oynaklık"),
        "yüksek": ("🔴", "yüksek oynaklık"),
    }.get(level or "", _NA)


def badge_trend_persistence(age_days: int | None) -> tuple[str, str]:
    if not age_days:
        return _NA
    if age_days <= 10:
        return "🟡", "çok taze — henüz kanıtlanmamış"
    if age_days <= 90:
        return "🟡", "kısa süreli"
    if age_days <= 250:
        return "🟢", "orta vadeli, oturmuş"
    return "🟢", "uzun soluklu, kalıcı"


def badge_health(score: float | None) -> tuple[str, str]:
    if score is None:
        return _NA
    if score >= 70:
        return "🟢", "sağlam bilanço"
    if score >= 40:
        return "🟡", "orta"
    return "🔴", "zayıf bilanço"


def fmt_badge(pair: tuple[str, str]) -> str:
    emoji, text = pair
    return f"{emoji} {text}"
