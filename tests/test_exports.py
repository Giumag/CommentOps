from src.exporters import backlog_to_csv, backlog_to_markdown


SAMPLE = [
    {
        "priority": "P0",
        "type": "Support",
        "need": "Export crash",
        "demand_score": 95,
        "comments": 10,
        "likes": 100,
        "recommended_action": "Investigate",
        "rationale": "Repeated failures",
    }
]


def test_backlog_csv_export():
    output = backlog_to_csv(SAMPLE).decode("utf-8")
    assert "Export crash" in output
    assert "Support" in output


def test_backlog_markdown_export():
    output = backlog_to_markdown(SAMPLE)
    assert "# Creator Backlog" in output
    assert "## P0" in output
    assert "Export crash" in output
