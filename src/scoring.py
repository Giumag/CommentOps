def demand_score(cluster_size: int, total_likes: int, avg_priority: float) -> int:
    """
    Transparent heuristic score from 0 to 100.
    Rewards repetition, engagement and urgency.
    """
    repetition = min(cluster_size / 8, 1.0) * 45
    engagement = min(total_likes / 100, 1.0) * 25
    urgency = min(avg_priority / 100, 1.0) * 30
    return round(min(repetition + engagement + urgency, 100))
