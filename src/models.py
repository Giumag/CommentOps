from dataclasses import dataclass

@dataclass
class CommentAnalysis:
    text: str
    category: str
    priority: int
    reason: str
