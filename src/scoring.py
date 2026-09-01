from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class DemandBreakdown:
    score: int
    recurrence: float
    engagement: float
    urgency: float
    freshness: float | None
    recurrence_max: int = 35
    engagement_max: int = 25
    urgency_max: int = 25
    freshness_max: int = 15

    @property
    def freshness_available(self) -> bool:
        return self.freshness is not None


def _parse_timestamp(value) -> datetime | None:
    if value is None:
        return None

    try:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None

    if pd.isna(ts):
        return None

    return ts.to_pydatetime()


def _freshness_points(
    published_at: Iterable,
    *,
    reference_time: datetime | None = None,
) -> float | None:
    timestamps = [
        parsed
        for value in published_at
        if (parsed := _parse_timestamp(value)) is not None
    ]

    if not timestamps:
        return None

    now = reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Exponential recency decay with a 45-day half-life.
    # A comment 45 days old keeps 50% of its freshness signal,
    # while older but still relevant conversations are not hard-cut.
    half_life_days = 45.0
    decay_constant = math.log(2) / half_life_days

    weights = []
    for timestamp in timestamps:
        age_days = max((now - timestamp).total_seconds() / 86400.0, 0.0)
        weights.append(math.exp(-decay_constant * age_days))

    # Use the mean recency of the cluster, with a small boost when several
    # comments are recent. This avoids a single fresh outlier dominating.
    mean_weight = sum(weights) / len(weights)
    recent_share = sum(1 for w in weights if w >= 0.5) / len(weights)

    blended = (mean_weight * 0.8) + (recent_share * 0.2)
    return min(blended, 1.0) * 15.0


def demand_breakdown(
    cluster_size: int,
    total_likes: int,
    avg_priority: float,
    published_at: Iterable | None = None,
    *,
    reference_time: datetime | None = None,
) -> DemandBreakdown:
    """
    Explainable 0–100 prioritization score.

    Signals:
      - recurrence: up to 35 points
      - engagement: up to 25 points
      - urgency: up to 25 points
      - freshness: up to 15 points, when timestamps exist

    If freshness is unavailable, the score is normalized across the
    remaining 85 available points rather than inventing a date signal.
    """

    cluster_size = max(int(cluster_size), 0)
    total_likes = max(int(total_likes), 0)
    avg_priority = max(min(float(avg_priority), 100.0), 0.0)

    recurrence = min(cluster_size / 8.0, 1.0) * 35.0

    # Log scaling prevents one viral comment from saturating the score
    # too aggressively while still rewarding meaningful engagement.
    engagement_scale = math.log1p(250)
    engagement = min(math.log1p(total_likes) / engagement_scale, 1.0) * 25.0

    urgency = (avg_priority / 100.0) * 25.0

    freshness = None
    if published_at is not None:
        freshness = _freshness_points(
            published_at,
            reference_time=reference_time,
        )

    raw = recurrence + engagement + urgency
    available_max = 35 + 25 + 25

    if freshness is not None:
        raw += freshness
        available_max += 15

    score = round((raw / available_max) * 100) if available_max else 0

    return DemandBreakdown(
        score=max(0, min(score, 100)),
        recurrence=round(recurrence, 1),
        engagement=round(engagement, 1),
        urgency=round(urgency, 1),
        freshness=round(freshness, 1) if freshness is not None else None,
    )


def demand_score(
    cluster_size: int,
    total_likes: int,
    avg_priority: float,
    published_at: Iterable | None = None,
) -> int:
    """Backward-compatible score-only helper."""
    return demand_breakdown(
        cluster_size,
        total_likes,
        avg_priority,
        published_at,
    ).score
