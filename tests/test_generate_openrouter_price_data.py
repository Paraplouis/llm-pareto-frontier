import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from utils.generate_openrouter_price_data import (
    author_labels,
    provider_display_name,
    extract_model_name,
    convert_openrouter,
)


class TestProviderDisplayName:
    def test_known_providers(self):
        assert provider_display_name("openai", {}) == "OpenAI"
        assert provider_display_name("meta-llama", {}) == "Meta"
        assert provider_display_name("deepseek", {}) == "DeepSeek"
        assert provider_display_name("xiaomi", {}) == "Xiaomi"

    def test_mapping_wins_over_openrouter_label(self):
        assert provider_display_name("x-ai", {"x-ai": "SpaceXAI"}) == "xAI"

    def test_unmapped_provider_uses_openrouter_label(self):
        assert provider_display_name("z-ai", {"z-ai": "Z.ai"}) == "Z.ai"

    def test_unknown_provider_titlecased(self):
        assert provider_display_name("some-new-lab", {}) == "Some New Lab"


class TestAuthorLabels:
    def test_reads_author_prefix_of_model_names(self):
        models = [
            {"id": "inclusionai/ling-flash-2.0", "name": "inclusionAI: Ling-flash-2.0"},
            {"id": "gryphe/mythomax-l2-13b", "name": "MythoMax 13B"},
        ]
        assert author_labels(models) == {"inclusionai": "inclusionAI"}


class TestExtractModelName:
    def test_standard_id(self):
        assert extract_model_name("meta-llama/llama-4-maverick") == "llama-4-maverick"

    def test_no_slash(self):
        assert extract_model_name("standalone-model") == "standalone-model"


class TestConvertOpenrouter:
    def test_basic_conversion(self):
        models = [
            {
                "id": "deepseek/deepseek-chat",
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
            }
        ]
        providers = convert_openrouter(models)
        assert providers == [
            {
                "provider": "DeepSeek",
                "models": [
                    {"name": "deepseek-chat", "inputPrice": pytest.approx(1.0), "outputPrice": pytest.approx(2.0)}
                ],
            }
        ]

    def test_skips_free_models(self):
        models = [
            {"id": "free/model", "pricing": {"prompt": "0", "completion": "0"}},
        ]
        assert convert_openrouter(models) == []

    def test_skips_missing_pricing(self):
        models = [{"id": "x/y", "pricing": None}]
        assert convert_openrouter(models) == []

    def test_skips_latest_aliases(self):
        models = [
            {"id": "~anthropic/claude-opus-latest", "pricing": {"prompt": "0.000004", "completion": "0.00002"}},
        ]
        assert convert_openrouter(models) == []

    def test_groups_unmapped_author_under_openrouter_label(self):
        models = [
            {"id": "z-ai/glm-5.3", "name": "Z.ai: GLM 5.3", "pricing": {"prompt": "0.0000003", "completion": "0.0000012"}},
        ]
        assert convert_openrouter(models)[0]["provider"] == "Z.ai"

    def test_skips_negative_sentinel_prices(self):
        models = [
            {"id": "openrouter/auto", "pricing": {"prompt": "-1", "completion": "-1"}},
        ]
        assert convert_openrouter(models) == []

    def test_deduplicates_provider_models_by_cheapest_input_price(self):
        models = [
            {"id": "openai/gpt-4o", "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
            {"id": "openai/gpt-4o", "pricing": {"prompt": "0.0000015", "completion": "0.000006"}},
        ]
        providers = convert_openrouter(models)
        model = providers[0]["models"][0]
        assert model["inputPrice"] == pytest.approx(1.5)
        assert model["outputPrice"] == pytest.approx(6.0)
