from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class BacklogRoute:
    work_type: str
    priority_band: str
    action: str
    rationale: str


SUPPORT_PATTERNS = (
    r"\bbug\b", r"\bcrash", r"\berror\b", r"\bfail", r"\bbroken\b",
    r"\bdoesn'?t work\b", r"\bcan't\b", r"\bcannot\b", r"\bissue\b",
    r"\blogin\b", r"\bsign in\b", r"\bauthentication\b",
)

DOCUMENTATION_PATTERNS = (
    r"\binstall", r"\bsetup\b", r"\bconfiguration\b", r"\bdocs?\b",
    r"\bguide\b", r"\bsteps?\b", r"\bhow do i get\b",
)

CONTENT_PATTERNS = (
    r"\btutorial\b", r"\bvideo\b", r"\bwalkthrough\b",
    r"\bnext video\b", r"\bcover\b", r"\bdeployment\b",
)

EDUCATION_PATTERNS = (
    r"\bwhy\b", r"\bexplain\b", r"\bunderstand\b", r"\bhow does\b",
    r"\barchitecture\b", r"\bdatabase\b", r"\bmemory\b", r"\bram\b",
)

COMMUNITY_PATTERNS = (
    r"\bfaq\b", r"\bpinned\b", r"\bpin\b", r"\breply\b",
)


def _matches(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def route_audience_need(
    comments: Iterable[str],
    *,
    avg_priority: float,
    cluster_size: int,
    demand_score: int,
) -> BacklogRoute:
    """
    Route an audience need into creator work.

    Ordering is deliberate:
    operational failures > documentation gaps > explicit content requests >
    educational confusion > community response.
    """
    comments = [str(c).strip() for c in comments if str(c).strip()]
    text = " ".join(comments).lower()

    if _matches(text, SUPPORT_PATTERNS):
        work_type = "Support"
        action = "Investigate before replying individually"
        rationale = "Repeated comments describe a failure or blocked user flow."

    elif _matches(text, DOCUMENTATION_PATTERNS):
        work_type = "Documentation"
        action = "Create or improve the canonical guide"
        rationale = "The audience is repeatedly missing setup or usage information."

    elif _matches(text, CONTENT_PATTERNS):
        work_type = "Content"
        action = "Add a focused piece to the content roadmap"
        rationale = "Viewers are explicitly requesting a tutorial or follow-up."

    elif _matches(text, EDUCATION_PATTERNS):
        work_type = "Education"
        action = "Explain the concept once, then reuse the explanation"
        rationale = "The cluster reflects recurring conceptual confusion."

    else:
        work_type = "Community"
        action = "Reply once and reuse the answer"
        rationale = "The audience need is recurring but does not require product work."

    # Priority reflects both demand and operational urgency.
    if work_type == "Support" and avg_priority >= 85:
        priority_band = "P0"
    elif demand_score >= 85:
        priority_band = "P1"
    elif demand_score >= 65:
        priority_band = "P2"
    else:
        priority_band = "P3"

    return BacklogRoute(
        work_type=work_type,
        priority_band=priority_band,
        action=action,
        rationale=rationale,
    )
