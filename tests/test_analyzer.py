from src.analyzer import classify_comment
from src.scoring import demand_score

def test_question_is_actionable():
    category, priority, _ = classify_comment("How do I install this?")
    assert category == "reply_now"
    assert priority >= 70

def test_spam_detection():
    category, _, _ = classify_comment("Check my channel https://example.com")
    assert category == "spam"

def test_demand_score_bounds():
    assert 0 <= demand_score(100, 10000, 100) <= 100
