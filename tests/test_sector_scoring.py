"""Sektör-göreceli puanlama — score_metrics(sector_stats=) (saf, ağ yok)."""

from __future__ import annotations

from src.analysis.scoring import _relative_points, score_metrics
from src.models import Market

_STATS = {"sectors": {
    "Technology": {"pe_median": 25, "pb_median": 8, "count": 12},
    "Banks": {"pe_median": 5, "pb_median": 0.9, "count": 8},
}}


def test_relative_points_ucuz_pahali_notr():
    assert _relative_points(10, 25, cheap_pts=15, exp_pts=-8)[0] == 15   # <0.7x
    assert _relative_points(25, 25, cheap_pts=15, exp_pts=-8)[0] == 0    # ~1x
    assert _relative_points(40, 25, cheap_pts=15, exp_pts=-8)[0] == -8   # >1.3x


def test_teknoloji_hissesi_fk18_sektorel_ucuz():
    m = {"sector": "Technology", "pe_trailing": 16}
    s = score_metrics(m, Market.US, _STATS)
    assert s.total > score_metrics(m, Market.US).total   # sektörel daha yüksek
    assert any("sektör medyanının" in r.label for r in s.reasons)


def test_sektor_taninmazsa_mutlak_esige_duser():
    m = {"sector": "Utilities", "pe_trailing": 12}   # _STATS'ta yok
    s_rel = score_metrics(m, Market.US, _STATS)
    s_abs = score_metrics(m, Market.US)
    assert s_rel.total == s_abs.total


def test_sector_stats_none_mutlak():
    m = {"sector": "Technology", "pe_trailing": 16}
    assert score_metrics(m, Market.US, None).total == score_metrics(m, Market.US).total
