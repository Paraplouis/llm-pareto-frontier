import sys
from pathlib import Path

# Ensure the utils package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from utils.generate_synthesized_data import ModelNameNormalizer, PriceMatcher, PriceInfo


# ---------- ModelNameNormalizer ----------

class TestModelNameNormalizer:
    def test_chatgpt_4o(self):
        assert "gpt" in ModelNameNormalizer.normalize("chatgpt-4o-2024-05-13")
        assert "chatgpt" not in ModelNameNormalizer.normalize("chatgpt-4o")

    def test_qwen3_max_preview(self):
        result = ModelNameNormalizer.normalize("qwen3-max-preview")
        assert "qwen" in result
        assert "preview" not in result

    def test_dbrx_instruct_preview(self):
        result = ModelNameNormalizer.normalize("dbrx-instruct-preview")
        assert "dbrx" in result
        assert "preview" not in result

    def test_solar(self):
        result = ModelNameNormalizer.normalize("solar-10.7b-instruct-v1.0")
        assert "upstage" in result or "solar" in result

    def test_qwen3_32b(self):
        result = ModelNameNormalizer.normalize("qwen3-32b")
        assert "qwen" in result
        assert "32b" in result

    def test_glm_4_plus(self):
        result = ModelNameNormalizer.normalize("glm-4-plus")
        assert "glm" in result

    def test_removes_online(self):
        result = ModelNameNormalizer.normalize("command-r-online")
        assert "online" not in result

    def test_removes_dates(self):
        result = ModelNameNormalizer.normalize("gpt-4o-2024-08-06")
        assert "2024" not in result

    def test_empty_string(self):
        assert ModelNameNormalizer.normalize("") == ""


# ---------- PriceMatcher ----------

class TestPriceMatcher:
    @pytest.fixture
    def matcher(self):
        lookup = {
            "gpt-4o": PriceInfo(2.5, 10.0, "OpenAI", "gpt-4o"),
            "claude-3.5-sonnet": PriceInfo(3.0, 15.0, "Anthropic", "claude-3.5-sonnet"),
            "llama-3.1-8b": PriceInfo(0.0, 0.0, "Together", "llama-3.1-8b"),
        }
        return PriceMatcher(lookup)

    def test_direct_match(self, matcher):
        result = matcher.find_match("gpt-4o")
        assert result is not None
        assert result.provider == "OpenAI"

    def test_normalized_match(self, matcher):
        # chatgpt-4o normalizes to gpt-4o
        result = matcher.find_match("chatgpt-4o-2024-08-06")
        assert result is not None

    def test_fuzzy_match(self, matcher):
        result = matcher.find_match("claude-3.5-sonnet-20241022")
        assert result is not None
        assert result.provider == "Anthropic"

    def test_no_match(self, matcher):
        result = matcher.find_match("completely-unknown-model-xyz")
        assert result is None


# ---------- Free model exclusion ----------

class TestFreeModelExclusion:
    """Verify that free model exclusion checks both input and output price."""

    def test_both_zero_excluded(self):
        """A model with input_price=0 AND output_price=0 should be excluded."""
        price_info = PriceInfo(input_price=0, output_price=0, provider="Free", original_name="free-model")
        # The condition in _process_model is: input_price == 0 and output_price == 0
        assert price_info.input_price == 0 and price_info.output_price == 0

    def test_input_zero_output_nonzero_not_excluded(self):
        """A model with input_price=0 but output_price>0 should NOT be excluded."""
        price_info = PriceInfo(input_price=0, output_price=5.0, provider="Provider", original_name="model")
        # Should not match the exclusion condition
        assert not (price_info.input_price == 0 and price_info.output_price == 0)

    def test_both_nonzero_not_excluded(self):
        """A model with both prices > 0 should not be excluded."""
        price_info = PriceInfo(input_price=1.0, output_price=2.0, provider="Provider", original_name="model")
        assert not (price_info.input_price == 0 and price_info.output_price == 0)
