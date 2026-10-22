import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from utils.generate_synthesized_data import PriceInfo, PriceMatcher, name_key, synthesize

class TestNameKey:
    def test_ignores_bracketed_settings_and_release_words(self):
        assert name_key("Claude Opus 4.6 (Thinking 32K)") == name_key("claude-opus-4.6")
        assert name_key("Qwen3.5-Flash Preview") == name_key("qwen3.5-flash")

    def test_reads_snapshot_dates_in_any_spelling(self):
        assert name_key("GPT-4o (2024-08-06)") == name_key("gpt-4o-2024-08-06")
        assert name_key("DeepSeek-V3 (0324)") == name_key("deepseek-chat-v3-0324")
        assert name_key("Claude Opus 4.6 (Thinking 32K, 20250219)").snapshots == {"20250219"}

    def test_reads_hyphenated_versions(self):
        assert name_key("Mistral Medium 3.5") == name_key("mistral-medium-3-5")
        assert name_key("Mistral Large 4") == name_key("mistral-large-4-0")

    def test_keeps_size_after_version(self):
        assert name_key("gemma-3-4b-it").sizes == {"4b"}

    def test_separates_sizes_from_words(self):
        key = name_key("Llama 4 Maverick 17B 128E Instruct")
        assert key.words == {"llama", "4", "maverick"}
        assert key.sizes == {"17b", "128e"}

class TestPriceMatcher:
    @pytest.fixture
    def matcher(self):
        lookup = {
            "gpt-4o": PriceInfo(2.5, 10.0, "OpenAI", "gpt-4o"),
            "claude-opus-5.5": PriceInfo(4.0, 20.0, "Anthropic", "claude-opus-5.5"),
            "qwen3.5-flash-02-23": PriceInfo(0.1, 0.4, "Alibaba", "qwen3.5-flash-02-23"),
            "qwen3.5-plus-20260420": PriceInfo(0.4, 2.4, "Alibaba", "qwen3.5-plus-20260420"),
            "gpt-4o-2024-05-13": PriceInfo(5.0, 15.0, "OpenAI", "gpt-4o-2024-05-13"),
            "mistral-large": PriceInfo(2.0, 6.0, "Mistral", "mistral-large"),
            "mistral-large-2512": PriceInfo(0.5, 1.5, "Mistral", "mistral-large-2512"),
            "hy3": PriceInfo(0.132, 0.528, "Tencent", "hy3"),
            "hy3-preview": PriceInfo(0.18, 0.6, "Tencent", "hy3-preview"),
            "command-r-08-2024": PriceInfo(0.15, 0.6, "Cohere", "command-r-08-2024"),
            "command-r7b-12-2024": PriceInfo(0.0375, 0.15, "Cohere", "command-r7b-12-2024"),
            "command-r-plus-08-2024": PriceInfo(2.5, 10.0, "Cohere", "command-r-plus-08-2024"),
            "deepseek-v3.2": PriceInfo(0.28, 0.42, "DeepSeek", "deepseek-v3.2"),
            "deepseek-v3.2-exp": PriceInfo(0.27, 0.41, "DeepSeek", "deepseek-v3.2-exp"),
            "llama-4-maverick": PriceInfo(0.15, 0.6, "Meta", "llama-4-maverick"),
            "gemma-2-27b-it": PriceInfo(0.65, 0.65, "Google", "gemma-2-27b-it"),
            "nemotron-3-super-120b-a12b": PriceInfo(0.1, 0.5, "NVIDIA", "nemotron-3-super-120b-a12b"),
        }
        return PriceMatcher(lookup)

    def test_prefers_same_snapshot(self, matcher):
        assert matcher.find_match("GPT-4o (2024-05-13)").original_name == "gpt-4o-2024-05-13"

    def test_falls_back_to_undated_entry_for_unlisted_snapshot(self, matcher):
        assert matcher.find_match("GPT-4o (2024-08-06)").original_name == "gpt-4o"
        assert matcher.find_match("Mistral Large (2402)").original_name == "mistral-large"

    def test_exact_name_ignores_spaces_versus_hyphens(self, matcher):
        assert matcher.find_match("Hy3 preview").original_name == "hy3-preview"

    def test_rejects_another_version(self, matcher):
        assert matcher.find_match("Claude 3 Opus (20240229)") is None

    def test_rejects_another_tier(self, matcher):
        assert matcher.find_match("Qwen3.5-Max-Preview") is None
        assert matcher.find_match("Qwen3.5-Flash").original_name == "qwen3.5-flash-02-23"

    def test_prefers_exact_name_over_cheaper_variant(self, matcher):
        assert matcher.find_match("DeepSeek-V3.2 (Thinking)").original_name == "deepseek-v3.2"

    def test_accepts_size_given_on_one_side_only(self, matcher):
        assert matcher.find_match("Llama 4 Maverick 17B 128E Instruct").original_name == "llama-4-maverick"

    def test_prefers_entry_without_size_when_name_gives_none(self, matcher):
        assert matcher.find_match("Command R").original_name == "command-r-08-2024"

    def test_reads_plus_as_a_word(self, matcher):
        assert matcher.find_match("Command R+").original_name == "command-r-plus-08-2024"

    def test_rejects_another_size(self, matcher):
        assert matcher.find_match("Gemma 2 9B IT") is None

    def test_uses_override_for_unmatchable_names(self):
        lookup = {"nova-2-lite-v1": PriceInfo(0.3, 2.5, "Amazon", "nova-2-lite-v1")}
        assert PriceMatcher(lookup).find_match("Amazon Nova 2 Lite").original_name == "nova-2-lite-v1"

    def test_ignores_author_name_in_model_name(self, matcher):
        result = matcher.find_match("NVIDIA-Nemotron-3-Super-120B-A12B")
        assert result.original_name == "nemotron-3-super-120b-a12b"

def test_synthesize_keeps_priced_models_above_min_elo():
    matcher = PriceMatcher({"gpt-4o": PriceInfo(2.5, 10.0, "OpenAI", "gpt-4o")})
    ranked = [
        {"Model": "GPT-4o (2024-08-06)", "Score": "1300", "Votes": "5000", "organization": "OpenAI"},
        {"Model": "Unlisted Model", "Score": "1200", "Votes": "10", "organization": "N/A"},
        {"Model": "gpt-4o", "Score": "999", "Votes": "10", "organization": "OpenAI"},
    ]

    records, debug = synthesize(ranked, matcher)

    assert records == [{
        "model": "GPT-4o (2024-08-06)",
        "elo": 1300,
        "input_price": 2.5,
        "output_price": 10.0,
        "votes": 5000,
        "organization": "OpenAI",
    }]
    assert [d["matched_price_model"] for d in debug] == ["gpt-4o", "No match found"]
