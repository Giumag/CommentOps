from src.backlog import route_audience_need


def test_bug_routes_to_support_p0():
    result = route_audience_need(
        ["The app crashes every time I export", "Export is broken"],
        avg_priority=90,
        cluster_size=2,
        demand_score=92,
    )
    assert result.work_type == "Support"
    assert result.priority_band == "P0"


def test_installation_routes_to_documentation():
    result = route_audience_need(
        ["How do I install this on Windows?", "Can you show setup steps?"],
        avg_priority=75,
        cluster_size=2,
        demand_score=80,
    )
    assert result.work_type == "Documentation"


def test_tutorial_request_routes_to_content():
    result = route_audience_need(
        ["Please make a deployment tutorial", "Would love a deployment video"],
        avg_priority=75,
        cluster_size=2,
        demand_score=78,
    )
    assert result.work_type == "Content"


def test_concept_question_routes_to_education():
    result = route_audience_need(
        ["Why does Docker use so much RAM?", "Can you explain Docker memory?"],
        avg_priority=75,
        cluster_size=2,
        demand_score=70,
    )
    assert result.work_type == "Education"


def test_generic_recurring_question_routes_to_community():
    result = route_audience_need(
        ["Will there be part two?", "Will there be another part?"],
        avg_priority=70,
        cluster_size=2,
        demand_score=55,
    )
    assert result.work_type == "Community"
