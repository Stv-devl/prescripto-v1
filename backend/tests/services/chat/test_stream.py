from mistralai.models import UsageInfo

from app.services.chat.stream import _usage_event, _usage_leg


class TestUsageLeg:
    def test_none_usage_is_all_zeros(self) -> None:
        assert _usage_leg(None) == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }

    def test_full_usage_computes_cost_from_both_token_counts(self) -> None:
        usage = UsageInfo(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            total_tokens=1_500_000,
        )
        assert _usage_leg(usage) == {
            "input_tokens": 1_000_000,
            "output_tokens": 500_000,
            "cost_usd": 1.25,
        }

    def test_none_prompt_tokens_on_a_present_usage_counts_as_zero_input(self) -> None:
        usage = UsageInfo(
            prompt_tokens=None,
            completion_tokens=2_000_000,
            total_tokens=2_000_000,
        )
        assert _usage_leg(usage) == {
            "input_tokens": 0,
            "output_tokens": 2_000_000,
            "cost_usd": 3.0,
        }


class TestUsageEvent:
    def test_both_legs_none_zeroes_rewrite_generation_and_total(self) -> None:
        assert _usage_event(None, None) == {
            "rewrite": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "generation": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        }

    def test_only_generation_set_leaves_rewrite_zeroed_and_total_equal_to_generation(
        self,
    ) -> None:
        generation = UsageInfo(
            prompt_tokens=200_000,
            completion_tokens=100_000,
            total_tokens=300_000,
        )
        event = _usage_event(None, generation)
        assert event["rewrite"] == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        assert event["generation"] == {
            "input_tokens": 200_000,
            "output_tokens": 100_000,
            "cost_usd": 0.25,
        }
        assert event["total"] == {
            "input_tokens": 200_000,
            "output_tokens": 100_000,
            "cost_usd": 0.25,
        }

    def test_both_legs_set_sums_elementwise_into_total(self) -> None:
        rewrite = UsageInfo(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            total_tokens=1_500_000,
        )
        generation = UsageInfo(
            prompt_tokens=200_000,
            completion_tokens=100_000,
            total_tokens=300_000,
        )
        event = _usage_event(rewrite, generation)
        assert event["total"] == {
            "input_tokens": 1_200_000,
            "output_tokens": 600_000,
            "cost_usd": 1.5,
        }
