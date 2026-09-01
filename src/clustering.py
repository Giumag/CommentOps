from __future__ import annotations

from collections import Counter
import math
import re


# Canonicalize common linguistic variants. These are language-level aliases,
# not topic labels: the clusterer still discovers recurring anchors from the data.
PHRASE_PATTERNS = (
    (r"\bwindows\s*11\b|\bwin11\b", "windows"),
    (r"\bmacos\b|\bmacbook\b|\bapple silicon\b", "mac"),
    (r"\blocalhost to production\b|\bfrom localhost to production\b", "deployment"),
    (r"\bdeploy(?:ed|ing)?\b", "deployment"),
    (r"\bsign[\s-]?in\b|\blog in\b|\bauthentication\b", "login"),
    (r"\bpassword reset\b|\breset(?:ting)? my password\b", "reset"),
    (r"\bmemory\b", "ram"),
    (r"\bcrashes\b|\bcrashed\b|\bcrashing\b", "crash"),
    (r"\bfails\b|\bfailing\b|\bfailure\b|\bbroken\b", "fail"),
    (r"\binstalling\b|\binstallation\b", "install"),
    (r"\bunit tests?\b|\bunit testing\b|\bautomated tests?\b", "testing"),
    (r"\btests?\b|\btesting\b", "testing"),
)

# Generic workflow/request terms are deliberately excluded from topic anchors.
# This prevents words such as "install", "crash", or "guide" from merging
# otherwise unrelated audience needs.
GENERIC_TERMS = {
    "how", "why", "what", "when", "where", "which", "who", "can", "could",
    "would", "should", "is", "are", "do", "does", "i", "me", "my", "this",
    "that", "the", "a", "an", "it", "to", "of", "for", "on", "you", "your",
    "we", "our", "in", "and", "or", "please", "make", "video", "tutorial",
    "guide", "walkthrough", "explain", "show", "help", "really", "useful",
    "love", "proper", "step", "steps", "another", "next", "work", "working",
    "get", "running", "app", "project", "issue", "problem", "fix", "fail",
    "crash", "every", "time", "keeps", "after", "before", "with", "about",
    "now", "new", "page", "button", "process", "setup", "clear", "confusing",
    "confused", "normal", "expected", "huge", "high", "reduce", "much", "too",
    "lot", "write", "add", "cover", "have", "there", "from", "into", "up",
    "be", "not", "dont", "doesnt", "cant", "isnt", "im", "was", "as", "soon",
    "click", "press", "install", "doesn", "using", "usage", "so", "password",
    "reset", "changing",
}


def _tokens(text: str) -> set[str]:
    text = (text or "").lower()

    for pattern, replacement in PHRASE_PATTERNS:
        text = re.sub(pattern, replacement, text)

    text = re.sub(r"[^a-z0-9_\s]", " ", text)

    return {
        token
        for token in text.split()
        if len(token) > 1 and token not in GENERIC_TERMS
    }


def group_similar_comments(texts: list[str]) -> list[int]:
    """
    Conservative recurring-anchor clustering.

    Instead of single-link semantic clustering (which can create giant chains),
    this method:
      1. extracts candidate topic anchors from the corpus itself;
      2. keeps only anchors recurring in multiple comments but not too broadly;
      3. links comments only when a substantial share of their anchors overlaps.

    Comments with no reliable recurring anchor stay separate rather than being
    force-merged. This is intentional: false merges are worse than extra groups
    in a creator inbox.
    """
    if not texts:
        return []

    if len(texts) == 1:
        return [0]

    docs = [_tokens(text) for text in texts]
    frequencies = Counter(token for doc in docs for token in doc)

    # On small datasets allow anchors recurring in up to 3 comments.
    # On larger datasets, an anchor must appear in <=20% of actionable comments
    # to remain specific enough to define a topic.
    max_anchor_frequency = max(3, math.ceil(len(docs) * 0.20))

    anchors = [
        {
            token
            for token in doc
            if 2 <= frequencies[token] <= max_anchor_frequency
        }
        for doc in docs
    ]

    parent = list(range(len(texts)))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if not anchors[i] or not anchors[j]:
                continue

            shared = anchors[i] & anchors[j]
            if not shared:
                continue

            union_set = anchors[i] | anchors[j]
            overlap = len(shared) / len(union_set)

            # Prevent one multi-topic comment from becoming a bridge that
            # collapses several otherwise distinct clusters.
            if overlap >= 0.50:
                union(i, j)

    root_to_cluster: dict[int, int] = {}
    result: list[int] = []

    for i in range(len(texts)):
        root = find(i)

        if root not in root_to_cluster:
            root_to_cluster[root] = len(root_to_cluster)

        result.append(root_to_cluster[root])

    return result
