import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen


DATASET_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DATASET_ID = "lmarena-ai/leaderboard-dataset"
CONFIG = "text"
SPLIT = "latest"
CATEGORY = "overall"
PAGE_SIZE = 100

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
}


def _organization_display_name(value: Any, model_name: str = "") -> str:
    """Convert dataset organization ids to display names used by the UI."""
    key = str(value or "").strip().lower()
    if key:
        return ORGANIZATION_NAMES.get(key, key.replace("-", " ").title())
    return MODEL_ORGANIZATION_OVERRIDES.get(model_name.lower(), "N/A")


def _fetch_rows_page(offset: int, length: int = PAGE_SIZE) -> Dict[str, Any]:
    """Fetch one page from Hugging Face's dataset server."""
    query = urlencode(
        {
            "dataset": DATASET_ID,
            "config": CONFIG,
            "split": SPLIT,
            "offset": offset,
            "length": length,
        }
    )
    with urlopen(f"{DATASET_ROWS_URL}?{query}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _convert_hf_row(row: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Convert a Hugging Face leaderboard row into the repo's rank_data schema."""
    if row.get("category") != CATEGORY:
        return None

    model_name = str(row.get("model_name") or "").strip()
    rating = row.get("rating")
    if not model_name or rating is None:
        return None

    try:
        score = str(int(round(float(rating))))
    except (TypeError, ValueError):
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


def fetch_latest_leaderboard_df() -> Tuple[Optional[List[Dict[str, str]]], Optional[str]]:
    """Download the current Text Arena overall leaderboard from Hugging Face.

    Returns:
        Tuple of (records with keys [Model, Score, Votes, organization], date string YYYY-MM-DD).
    """
    print("  ↳ Fetching LM Arena text leaderboard from Hugging Face dataset server...")

    records: List[Dict[str, str]] = []
    publish_dates: List[str] = []
    offset = 0
    total_rows: Optional[int] = None
    seen_overall = False

    while total_rows is None or offset < total_rows:
        try:
            payload = _fetch_rows_page(offset)
        except Exception as e:
            print(f"  ❌ Failed to fetch leaderboard rows at offset {offset}: {e}")
            return None, None

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
                published = row.get("leaderboard_publish_date")
                if published:
                    publish_dates.append(str(published)[:10])

        if stop_after_page:
            break

        offset += len(rows)

    if not records:
        print("  ❌ No overall leaderboard rows found in Hugging Face dataset response.")
        return None, None

    last_updated = max(publish_dates) if publish_dates else None
    print(f"  ↳ Loaded {len(records)} overall leaderboard rows (updated: {last_updated})")
    return records, last_updated


if __name__ == "__main__":
    leaderboard_df, file_date = fetch_latest_leaderboard_df()
    if leaderboard_df is not None and file_date is not None:
        output_path = Path(__file__).parent.parent / "data" / "rank_data.json"
        output_data = {"last_updated": file_date, "models": leaderboard_df}

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print("  ✅ Successfully saved LM Arena data to data/rank_data.json")
    else:
        print("  ❌ Failed to extract data.")
        print("\n❌ DATA REFRESH FAILED")
        sys.exit(1)
