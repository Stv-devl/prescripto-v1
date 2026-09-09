"""Unit tests for the fixed-window counter.

The clock is injected everywhere below. Nothing here waits for a real second,
and no assertion is made on elapsed time — a duration is the one thing this
suite cannot check without becoming flaky.
"""

from app.core.ratelimit import FixedWindowCounter, counter_for, reset_all


class _Clock:
    """A hand-cranked monotonic clock."""

    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class TestTheLimitBites:
    def test_the_first_calls_pass_and_the_next_one_is_refused(self) -> None:
        counter = FixedWindowCounter(limit=3, window_seconds=60, now=_Clock())

        assert [counter.hit("a").allowed for _ in range(3)] == [True, True, True]
        assert counter.hit("a").allowed is False

    def test_a_refusal_carries_a_delay_of_at_least_one_second(self) -> None:
        """A refusal that says nothing forces the client to poll — which is the
        behaviour this whole module exists to stop."""
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=_Clock())
        counter.hit("a")

        assert counter.hit("a").retry_after_seconds >= 1

    def test_an_allowed_call_carries_no_delay(self) -> None:
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=_Clock())

        assert counter.hit("a").retry_after_seconds == 0


class TestKeysAndBucketsAreIndependent:
    def test_exhausting_one_key_leaves_another_alone(self) -> None:
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=_Clock())
        counter.hit("a")

        assert counter.hit("a").allowed is False
        assert counter.hit("b").allowed is True

    def test_two_buckets_do_not_share_a_count_for_the_same_client(self) -> None:
        """Otherwise one limit governs several routes and nobody notices."""
        reset_all()
        login = counter_for("login", limit=1, window_seconds=60)
        signup = counter_for("signup", limit=1, window_seconds=60)

        login.hit("client")

        assert login.hit("client").allowed is False
        assert signup.hit("client").allowed is True


class TestTheWindowReopens:
    def test_the_same_key_passes_again_once_the_window_has_gone(self) -> None:
        clock = _Clock()
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=clock)
        counter.hit("a")

        clock.advance(61)

        assert counter.hit("a").allowed is True

    def test_the_announced_delay_shrinks_as_the_window_advances(self) -> None:
        clock = _Clock()
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=clock)
        counter.hit("a")

        early = counter.hit("a").retry_after_seconds
        clock.advance(30)
        late = counter.hit("a").retry_after_seconds

        assert late < early


class TestForgetting:
    def test_a_key_whose_window_has_passed_is_forgotten(self) -> None:
        clock = _Clock()
        counter = FixedWindowCounter(limit=5, window_seconds=60, now=clock)
        counter.hit("gone")

        clock.advance(61)
        counter.hit("fresh")

        assert counter.tracked_keys == 1

    def test_a_key_still_inside_its_window_is_never_evicted(self) -> None:
        """The case that forbids a cap which evicts live keys.

        An evicted key starts counting from zero, so a counter that dropped live
        keys under memory pressure would let ordinary traffic wipe the count of
        exactly the client the limit exists to slow down.
        """
        clock = _Clock()
        counter = FixedWindowCounter(limit=1, window_seconds=60, now=clock)
        counter.hit("victim")

        for index in range(5_000):
            counter.hit(f"crowd-{index}")

        assert counter.hit("victim").allowed is False


class TestEdges:
    def test_a_limit_of_zero_refuses_the_very_first_call(self) -> None:
        counter = FixedWindowCounter(limit=0, window_seconds=60, now=_Clock())

        assert counter.hit("a").allowed is False

    # The plan asked for a case proving `hit` stays exact under concurrent
    # threads — FastAPI runs a synchronous dependency in its pool, so the
    # read-modify-write really is reachable from several threads. It is NOT
    # here, and that is deliberate: removing the lock from `hit` leaves such a
    # case green under a start barrier, under a clock that releases the GIL, and
    # under sys.setswitchinterval(1e-6) — all three measured on CPython 3.12.
    # The lock stays, because it is correct and costs nothing; the assertion
    # does not, because one that cannot fail only silences the question. The
    # property is defended by reading, not by this suite.
