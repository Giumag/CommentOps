import pandas as pd

from src.analyzer import classify_comment
from src.clustering import group_similar_comments


def test_demo_regression_120_80_8():
    df = pd.read_csv("data/demo_comments_120.csv")

    analysis = df["comment"].fillna("").astype(str).apply(classify_comment)
    categories = [row[0] for row in analysis]
    actionable = df[[category == "reply_now" for category in categories]].copy()

    clusters = group_similar_comments(actionable["comment"].tolist())

    assert len(df) == 120
    assert len(actionable) == 80
    assert len(set(clusters)) == 8
