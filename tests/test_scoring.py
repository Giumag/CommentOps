from datetime import datetime, timezone

from src.scoring import demand_breakdown, demand_score


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_demand_score_bounds():
    assert 0 <= demand_score(100, 10000, 100) <= 100


def test_recurrence_increases_score():
    low = demand_score(1, 10, 75)
    high = demand_score(8, 10, 75)
    assert high > low


def test_engagement_increases_score():
    low = demand_score(4, 0, 75)
    high = demand_score(4, 200, 75)
    assert high > low


def test_urgency_increases_score():
    low = demand_score(4, 50, 25)
    high = demand_score(4, 50, 95)
    assert high > low


def test_freshness_increases_score_when_available():
    fresh = demand_breakdown(
        4,
        50,
        75,
        ["2026-08-31T12:00:00Z", "2026-08-30T12:00:00Z"],
        reference_time=NOW,
    )
    stale = demand_breakdown(
        4,
        50,
        75,
        ["2025-01-01T12:00:00Z", "2025-01-02T12:00:00Z"],
        reference_time=NOW,
    )

    assert fresh.freshness is not None
    assert stale.freshness is not None
    assert fresh.freshness > stale.freshness
    assert fresh.score > stale.score


def test_missing_dates_do_not_invent_freshness():
    result = demand_breakdown(4, 50, 75, [])
    assert result.freshness is None
