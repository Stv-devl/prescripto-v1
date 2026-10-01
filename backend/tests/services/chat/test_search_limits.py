from app.services.chat.search_limits import narrow_search_limit, query_limits


def test_limits_at_20_match_the_historical_formula() -> None:
    assert query_limits(20, main_queries=3, forced_queries=0) == (20, 20)
    assert query_limits(20, main_queries=5, forced_queries=2) == (25, 20)
    assert query_limits(20, main_queries=6, forced_queries=6) == (30, 30)


def test_limits_scale_the_per_query_floor_at_15() -> None:
    assert query_limits(15, main_queries=3, forced_queries=2) == (15, 15)
    assert query_limits(15, main_queries=6, forced_queries=6) == (18, 18)


def test_limits_scale_the_per_query_floor_at_10() -> None:
    assert query_limits(10, main_queries=3, forced_queries=0) == (10, 10)
    assert query_limits(10, main_queries=6, forced_queries=7) == (12, 14)


def test_v1_takes_the_configured_narrow_limit() -> None:
    assert narrow_search_limit("v1", 15) == 15


def test_baseline_ignores_the_configured_narrow_limit() -> None:
    assert narrow_search_limit("baseline", 10) == 20


def test_per_query_floor_never_drops_below_one() -> None:
    assert query_limits(3, main_queries=5, forced_queries=4) == (5, 4)


def test_limit_never_falls_under_the_search_limit() -> None:
    assert query_limits(10, main_queries=1, forced_queries=1) == (10, 10)


def test_zero_queries_keeps_the_search_limit() -> None:
    assert query_limits(10, main_queries=0, forced_queries=0) == (10, 10)
