import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


DATASET_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DATASET_ID = "lmarena-ai/leaderboard-dataset"
CONFIG = "text_style_control"
SPLIT = "latest"
CATEGORY = "overall"
PAGE_SIZE = 100
FETCH_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

ORGANIZATION_NAMES = {
    "": "N/A",
    "01.ai": "01.AI",
    "ai21": "AI21 Labs",
    "alibaba": "Alibaba",
    "allenai": "Allen AI",
    "ant group": "Ant Group",
    "amazon": "Amazon",
    "anthropic": "Anthropic",
    "baidu": "Baidu",
    "bytedance": "ByteDance",
    "cohere": "Cohere",
    "deepseek": "DeepSeek",
    "google": "Google",
    "ibm": "IBM",
    "inception ai": "Inception AI",
    "meta": "Meta",
    "microsoft": "Microsoft",
    "microsoft ai": "Microsoft AI",
    "minimax": "MiniMax",
    "mistral": "Mistral",
    "moonshot": "Moonshot",
    "nvidia": "Nvidia",
    "openai": "OpenAI",
    "reka": "Reka",
    "stepfun": "StepFun",
    "xai": "xAI",
    "z.ai": "Z.ai",
    "zai": "Z.ai",
    "zhipu": "Zhipu",
}

MODEL_ORGANIZATION_OVERRIDES = {
    "dolphin-2.2.1-mistral-7b": "Dolphin",
    "gemma-2-9b-it-simpo": "Princeton NLP",
    "intellect-3": "Prime Intellect",
    "jamba-1.5-large": "AI21 Labs",
    "openhermes-2.5-mistral-7b": "Teknium",
    "reka-flash-20240904": "Reka",
    "trinity-large-preview": "Arcee AI",
    "trinity-large-thinking": "Arcee AI",
}


def _organization_display_name(value: Any, model_name: str) -> str:
    """Convert dataset organization ids such as inception-ai to the display names used by the UI."""
    key = str(value or "").strip().lower().replace("-", " ")
    if key:
        return ORGANIZATION_NAMES.get(key, key.title())
    return MODEL_ORGANIZATION_OVERRIDES.get(model_name.lower(), "N/A")


def _read_json(url: str) -> Dict[str, Any]:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_rows_page(offset: int) -> Dict[str, Any]:
    """Fetch one page of rows, retrying server errors and timeouts before the last attempt."""
    query = urlencode({"dataset": DATASET_ID, "config": CONFIG, "split": SPLIT, "offset": offset, "length": PAGE_SIZE})
    url = f"{DATASET_ROWS_URL}?{query}"
    for attempt in range(1, FETCH_ATTEMPTS):
        try:
            return _read_json(url)
        except (URLError, TimeoutError) as e:
            if isinstance(e, HTTPError) and e.code < 500:
                raise
            print(f"  Retrying rows at offset {offset} after: {e} ({attempt}/{FETCH_ATTEMPTS})")
            time.sleep(RETRY_DELAY_SECONDS)
    return _read_json(url)


def _convert_hf_row(row: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Convert a leaderboard row into the rank_data schema, or None when its name or rating is unusable."""
    model_name = str(row.get("model_name") or "").strip()
    try:
        score = str(round(float(row["rating"])))
    except (KeyError, TypeError, ValueError):
        return None
    if not model_name:
        return None

    try:
        votes = str(int(float(row.get("vote_count") or 0)))
    except (TypeError, ValueError):
        votes = "0"

    return {
        "Model": model_name,
        "Score": score,
        "Votes": votes,
        "organization": _organization_display_name(row.get("organization"), model_name),
    }


def fetch_latest_leaderboard() -> Tuple[List[Dict[str, str]], str]:
    """Download the overall Text Arena (style control) leaderboard and its publication date."""
    print("  Fetching LM Arena text (style control) leaderboard from Hugging Face dataset server")

    records: List[Dict[str, str]] = []
    publish_dates: List[str] = []
    offset = 0
    total_rows: Optional[int] = None
    seen_overall = False

    # Rows are grouped by category; the overall block ends at the first row of the next category.
    while total_rows is None or offset < total_rows:
        payload = _fetch_rows_page(offset)
        rows = payload.get("rows", [])
        total_rows = int(payload.get("num_rows_total") or 0)
        if not rows:
            break

        stop_after_page = False
        for item in rows:
            row = item.get("row", {})
            if row.get("category") != CATEGORY:
                if seen_overall:
                    stop_after_page = True
                    break
                continue
            seen_overall = True
            converted = _convert_hf_row(row)
            if converted:
                records.append(converted)
                if row.get("leaderboard_publish_date"):
                    publish_dates.append(str(row["leaderboard_publish_date"])[:10])

        if stop_after_page:
            break
        offset += len(rows)

    if not records or not publish_dates:
        raise ValueError("No dated overall leaderboard rows in the Hugging Face dataset response")

    last_updated = max(publish_dates)
    print(f"  Loaded {len(records)} overall leaderboard rows (updated: {last_updated})")
    return records, last_updated


if __name__ == "__main__":
    models, last_updated = fetch_latest_leaderboard()
    output_path = Path(__file__).resolve().parent.parent / "data" / "rank_data.json"
    output_path.write_text(
        json.dumps({"last_updated": last_updated, "models": models}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("  Saved LM Arena data to data/rank_data.json")
