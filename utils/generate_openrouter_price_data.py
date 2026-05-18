"""Generate price_data.json from OpenRouter model pricing.

OpenRouter prices are per token; price_data.json uses per million tokens.

Usage:
    python3 generate_openrouter_price_data.py openrouter_raw.json
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


def provider_display_name(slug: str) -> str:
    """Convert an OpenRouter provider slug to the display name used by the app."""
    return PROVIDER_MAP.get(slug, slug.replace("-", " ").title())


def extract_model_name(model_id: str) -> str:
    """Extract the model portion from an OpenRouter id like meta-llama/llama-4."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def load_openrouter(path: Path) -> List[dict]:
    """Load the OpenRouter model list from a pre-downloaded JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        body = json.load(f)
    models = body.get("data", []) if isinstance(body, dict) else body
    print(f"  ↳ Loaded {len(models)} models from {path.name}")
    return models


def convert_openrouter(models: List[dict]) -> List[dict]:
    """Convert OpenRouter models into the price_data.json provider schema."""
    grouped: Dict[str, Dict[str, dict]] = {}
    skipped = 0

    for model in models:
        model_id = model.get("id", "")
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
        provider = provider_display_name(slug)
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
        {
            "provider": provider,
            "uri": "https://openrouter.ai",
            "models": list(models_by_name.values()),
        }
        for provider, models_by_name in sorted(grouped.items())
    ]

    total = sum(len(provider["models"]) for provider in price_data)
    print(f"  ↳ Converted {total} priced models across {len(price_data)} providers (skipped {skipped})")
    return price_data


def main() -> int:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    output_file = data_dir / "price_data.json"
    openrouter_file = Path(sys.argv[1]) if len(sys.argv) > 1 else data_dir / "openrouter_raw.json"

    try:
        models = load_openrouter(openrouter_file)
    except Exception as e:
        print(f"  ❌ Failed to load OpenRouter data: {e}")
        return 1

    price_data = convert_openrouter(models)
    if not price_data:
        print("  ❌ OpenRouter response did not contain any usable priced models.")
        return 1

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(price_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total_models = sum(len(provider.get("models", [])) for provider in price_data)
    print(f"  ✅ price_data.json updated from OpenRouter: {len(price_data)} providers, {total_models} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
