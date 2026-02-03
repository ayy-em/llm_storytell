"""Tests for LLM pricing and run cost estimation."""

from llm_storytell.llm.pricing import (
    MODEL_COST_PER_1M,
    estimate_run_cost,
    estimate_tts_cost,
)


class TestEstimateRunCost:
    """Tests for estimate_run_cost."""

    def test_empty_list_returns_none_model_and_zero_tokens(self) -> None:
        model, prompt, completion, total, cost = estimate_run_cost([])
        assert model is None
        assert prompt == 0
        assert completion == 0
        assert total == 0
        assert cost is None

    def test_known_model_returns_estimated_cost(self) -> None:
        usage = [
            {
                "step": "outline",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "prompt_tokens": 1_000_000,
                "completion_tokens": 500_000,
                "total_tokens": 1_500_000,
            }
        ]
        # gpt-4.1-mini: $0.40/1M input, $1.60/1M output -> 0.40 + 0.80 = 1.20
        model, prompt, completion, total, cost = estimate_run_cost(usage)
        assert model == "gpt-4.1-mini"
        assert prompt == 1_000_000
        assert completion == 500_000
        assert total == 1_500_000
        assert cost is not None
        assert abs(cost - 1.20) < 0.001

    def test_unknown_model_returns_none_cost(self) -> None:
        usage = [
            {
                "step": "outline",
                "provider": "openai",
                "model": "gpt-unknown-model",
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "total_tokens": 1500,
            }
        ]
        model, prompt, completion, total, cost = estimate_run_cost(usage)
        assert model == "gpt-unknown-model"
        assert prompt == 1000
        assert completion == 500
        assert cost is None

    def test_aggregates_multiple_entries(self) -> None:
        usage = [
            {
                "step": "outline",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            {
                "step": "section_00",
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
            },
        ]
        model, prompt, completion, total, cost = estimate_run_cost(usage)
        assert model == "gpt-4.1-mini"
        assert prompt == 300
        assert completion == 150
        assert total == 450
        assert cost is not None
        # 300 * 0.40/1e6 + 150 * 1.60/1e6 = 0.00012 + 0.00024 = 0.00036 -> rounded to 4 decimals
        assert abs(cost - 0.0004) < 0.00001

    def test_uses_first_entry_model(self) -> None:
        usage = [
            {"model": "gpt-4.1-mini", "prompt_tokens": 1, "completion_tokens": 0},
            {"model": "gpt-4.1-nano", "prompt_tokens": 1, "completion_tokens": 0},
        ]
        model, _, _, _, _ = estimate_run_cost(usage)
        assert model == "gpt-4.1-mini"

    def test_skips_non_dict_entries(self) -> None:
        usage = [
            {"model": "gpt-4.1-mini", "prompt_tokens": 10, "completion_tokens": 5},
            "invalid",
            None,
        ]
        model, prompt, completion, total, cost = estimate_run_cost(usage)
        assert model == "gpt-4.1-mini"
        assert prompt == 10
        assert completion == 5
        assert cost is not None

    def test_missing_token_fields_treated_as_zero(self) -> None:
        usage = [{"model": "gpt-4.1-mini"}]
        model, prompt, completion, total, cost = estimate_run_cost(usage)
        assert model == "gpt-4.1-mini"
        assert prompt == 0
        assert completion == 0
        assert total == 0
        assert cost is not None
        assert cost == 0.0


class TestEstimateTtsCost:
    """Tests for estimate_tts_cost."""

    def test_empty_list_returns_zero_chars_and_none_cost(self) -> None:
        total_chars, cost = estimate_tts_cost([])
        assert total_chars == 0
        assert cost is None

    def test_known_model_returns_estimated_cost(self) -> None:
        tts_usage = [
            {
                "step": "tts_01",
                "provider": "openai",
                "model": "tts-1",
                "input_characters": 1_000_000,
            }
        ]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 1_000_000
        assert cost is not None
        assert abs(cost - 15.0) < 0.001

    def test_unknown_model_returns_none_cost(self) -> None:
        tts_usage = [
            {
                "step": "tts_01",
                "provider": "openai",
                "model": "tts-unknown",
                "input_characters": 1000,
            }
        ]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 1000
        assert cost is None

    def test_aggregates_multiple_entries(self) -> None:
        tts_usage = [
            {
                "step": "tts_01",
                "model": "gpt-4o-mini-tts",
                "input_characters": 500_000,
            },
            {
                "step": "tts_02",
                "model": "gpt-4o-mini-tts",
                "input_characters": 500_000,
            },
        ]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 1_000_000
        assert cost is not None
        # 15.50 per 1M chars
        assert abs(cost - 15.50) < 0.001

    def test_uses_first_entry_model(self) -> None:
        tts_usage = [
            {"model": "tts-1", "input_characters": 100},
            {"model": "tts-1-hd", "input_characters": 100},
        ]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 200
        assert cost is not None
        # Rate from first entry (tts-1: $15/1M)
        assert abs(cost - (200 * 15.0 / 1_000_000)) < 0.0001

    def test_missing_input_characters_treated_as_zero(self) -> None:
        tts_usage = [{"model": "tts-1", "step": "tts_01"}]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 0
        assert cost is not None
        assert cost == 0.0

    def test_skips_non_dict_entries(self) -> None:
        tts_usage = [
            {"model": "tts-1", "input_characters": 100},
            "invalid",
            None,
        ]
        total_chars, cost = estimate_tts_cost(tts_usage)
        assert total_chars == 100
        assert cost is not None


class TestModelCostPer1M:
    """Sanity checks on pricing table."""

    def test_default_model_in_table(self) -> None:
        assert "gpt-4.1-mini" in MODEL_COST_PER_1M

    def test_entries_are_input_output_pairs(self) -> None:
        for model, pair in MODEL_COST_PER_1M.items():
            assert isinstance(pair, tuple), f"{model!r} value should be (input, output)"
            assert len(pair) == 2, f"{model!r} should have 2 values"
            assert pair[0] >= 0 and pair[1] >= 0, (
                f"{model!r} prices should be non-negative"
            )
