"""Convert an OpenRouter /models response into data/price_data.json, in USD per million tokens.

Usage: python3 generate_openrouter_price_data.py data/openrouter_raw.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List


PROVIDER_MAP: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta-llama": "Meta",
    "mistralai": "Mistral",
    "x-ai": "xAI",
    "deepseek": "DeepSeek",
    "cohere": "Cohere",
    "amazon": "Amazon",
    "microsoft": "Microsoft",
    "nvidia": "NVIDIA",
    "alibaba": "Alibaba",
    "qwen": "Alibaba",
    "zhipu": "Zhipu",
    "baidu": "Baidu",
    "bytedance": "ByteDance",
    "tencent": "Tencent",
    "stepfun": "StepFun",
    "xiaomi": "Xiaomi",
    "inception": "Inception",
    "ai21": "AI21 Labs",
    "allenai": "Allen AI",
    "perplexity": "Perplexity",
    "minimax": "MiniMax",
    "nousresearch": "Nous Research",
    "databricks": "Databricks",
    "01-ai": "01.AI",
    "thudm": "Zhipu",
}


ALIAS_PREFIX = "~"


def author_labels(models: List[dict]) -> Dict[str, str]:
    """Read OpenRouter's author label per id prefix from model names shaped "Author: Model"."""
    labels: Dict[str, str] = {}
    for model in models:
        slug = model.get("id", "").split("/", 1)[0]
        author, separator, _ = (model.get("name") or "").partition(": ")
        if separator:
            labels.setdefault(slug, author)
    return labels


def provider_display_name(slug: str, labels: Dict[str, str]) -> str:
    """Convert an OpenRouter author slug to the display name used by the app."""
    return PROVIDER_MAP.get(slug) or labels.get(slug) or slug.replace("-", " ").title()


def extract_model_name(model_id: str) -> str:
    """Extract the model portion from an OpenRouter id like meta-llama/llama-4."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def total_models(price_data: List[dict]) -> int:
    return sum(len(provider["models"]) for provider in price_data)


def convert_openrouter(models: List[dict]) -> List[dict]:
    """Group priced models by author, keeping the cheaper input price when an author lists a name twice."""
    grouped: Dict[str, Dict[str, dict]] = {}
    labels = author_labels(models)
    skipped = 0

    for model in models:
        model_id = model.get("id", "")
        # "~author/family-latest" ids redirect to whichever model is newest, so their price fits no fixed version.
        if model_id.startswith(ALIAS_PREFIX):
            skipped += 1
            continue
        pricing = model.get("pricing") or {}
        prompt_per_token = pricing.get("prompt")
        completion_per_token = pricing.get("completion")

        if not prompt_per_token or not completion_per_token:
            skipped += 1
            continue

        try:
            input_price = float(prompt_per_token) * 1_000_000
            output_price = float(completion_per_token) * 1_000_000
        except (TypeError, ValueError):
            skipped += 1
            continue

        if input_price <= 0 or output_price <= 0:
            skipped += 1
            continue

        slug = model_id.split("/", 1)[0] if "/" in model_id else "unknown"
        provider = provider_display_name(slug, labels)
        name = extract_model_name(model_id)
        entry = {
            "name": name,
            "inputPrice": round(input_price, 4),
            "outputPrice": round(output_price, 4),
        }

        provider_models = grouped.setdefault(provider, {})
        key = name.lower()
        existing = provider_models.get(key)
        if existing is None or entry["inputPrice"] < existing["inputPrice"]:
            provider_models[key] = entry

    price_data = [
        {"provider": provider, "models": list(models_by_name.values())}
        for provider, models_by_name in sorted(grouped.items())
    ]

    print(f"  Converted {total_models(price_data)} priced models across {len(price_data)} providers (skipped {skipped})")
    return price_data


def main() -> int:
    openrouter_file = Path(sys.argv[1])
    models = json.loads(openrouter_file.read_text(encoding="utf-8"))["data"]
    print(f"  Loaded {len(models)} models from {openrouter_file.name}")

    price_data = convert_openrouter(models)
    if not price_data:
        print("OpenRouter response did not contain any usable priced models.")
        return 1

    output_file = Path(__file__).resolve().parent.parent / "data" / "price_data.json"
    output_file.write_text(json.dumps(price_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  Saved {total_models(price_data)} models from {len(price_data)} providers to data/price_data.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
