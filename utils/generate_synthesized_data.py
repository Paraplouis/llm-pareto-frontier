import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MIN_ELO = 1000

# Tokens that name a release channel or packaging rather than a different model.
NAME_NOISE = {"a", "beta", "chat", "exp", "instruct", "it", "latest", "preview", "v"}

# Ranked names whose OpenRouter entry carries a version suffix the ranking omits, or the reverse.
PRICE_MODEL_OVERRIDES = {
    "Amazon Nova 2 Lite": "nova-2-lite-v1",
    "Mixtral 8x22B Instruct v0.1": "mixtral-8x22b-instruct",
}


@dataclass
class PriceInfo:
    input_price: float
    output_price: float
    provider: str
    original_name: str


@dataclass(frozen=True)
class NameKey:
    """Tokens that identify a model: family, tier and version words, parameter sizes, and snapshot dates."""

    words: FrozenSet[str]
    sizes: FrozenSet[str]
    snapshots: FrozenSet[str]


def name_key(name: str) -> NameKey:
    """Reduce a model name to its identifying tokens; bracketed settings such as (High) are dropped, dates kept."""
    name = name.lower().replace("+", " plus ")
    bracketed = " ".join(re.findall(r"\((.*?)\)", name))
    bracketed_dates = re.findall(r"(?<![\w.])(\d{4}-\d{2}-\d{2}|\d{2}-\d{2,4}|\d{4,}|0\d+)(?![\w.])", bracketed)
    name = re.sub(r"\(.*?\)", " ", name) + " " + " ".join(bracketed_dates)
    # Dates such as 2024-05-13, 09-2025 or 02-23 become one digit token.
    name = re.sub(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)|(?<!\d)(\d{2})-(\d{2,4})(?!\d)",
                  lambda m: "".join(g for g in m.groups() if g), name)
    # OpenRouter spells some versions with a hyphen, as in mistral-medium-3-5 or claude-3-5-sonnet.
    name = re.sub(r"(?<!\d)(\d)-(\d)(?![\w.])", r"\1.\2", name)
    words, sizes, snapshots = set(), set(), set()
    for token in re.findall(r"\d+x\d+b|[a-z]+|\d+(?:\.\d+)*[a-z]*", name):
        if token in NAME_NOISE or re.fullmatch(r"\d+k", token):
            continue
        if re.fullmatch(r"\d{4,}|0\d+", token):
            snapshots.add(token)
            continue
        token = re.sub(r"(?:\.0)+(?=[a-z]*$)", "", token)
        if re.fullmatch(r"\d+(?:\.\d+)?[be]|\d+x\d+b", token):
            sizes.add(token)
        else:
            words.add(token)
    return NameKey(frozenset(words), frozenset(sizes), frozenset(snapshots))


def same_model(rank: NameKey, price: NameKey, author: str) -> bool:
    """Same model when words agree apart from the author's own name, and sizes and snapshots agree where both give one."""
    author_words = set(re.findall(r"[a-z]+", author.lower()))
    sizes_agree = not rank.sizes or not price.sizes or rank.sizes == price.sizes
    snapshots_agree = not rank.snapshots or not price.snapshots or rank.snapshots == price.snapshots
    return rank.words - author_words == price.words - author_words and sizes_agree and snapshots_agree


class PriceMatcher:
    def __init__(self, price_lookup: Dict[str, PriceInfo]):
        self.price_lookup = price_lookup
        self.price_keys = {price_model: name_key(price_model) for price_model in price_lookup}

    def find_match(self, model_name: str) -> Optional[PriceInfo]:
        """Price of the same model, preferring the same snapshot, the exact name, the same sizes, then an undated entry."""
        if model_name in PRICE_MODEL_OVERRIDES:
            return self.price_lookup.get(PRICE_MODEL_OVERRIDES[model_name])
        key = name_key(model_name)
        candidates = [
            price_model
            for price_model, info in self.price_lookup.items()
            if same_model(key, self.price_keys[price_model], info.provider)
        ]
        if not candidates:
            return None

        exact = re.sub(r"\s*\(.*?\)", "", model_name).strip().lower().replace(" ", "-")

        def preference(price_model: str) -> tuple:
            price_key = self.price_keys[price_model]
            return (
                not (key.snapshots and price_key.snapshots == key.snapshots),
                price_model != exact,
                price_key.sizes != key.sizes,
                bool(price_key.snapshots),
                self.price_lookup[price_model].input_price,
            )

        return self.price_lookup[min(candidates, key=preference)]


def load_price_lookup(price_data: List[dict]) -> Dict[str, PriceInfo]:
    """Index prices by lowercased model name, keeping the cheaper input price when two authors list one name."""
    lookup: Dict[str, PriceInfo] = {}
    for provider in price_data:
        for model in provider["models"]:
            key = model["name"].lower()
            if key not in lookup or model["inputPrice"] < lookup[key].input_price:
                lookup[key] = PriceInfo(model["inputPrice"], model["outputPrice"], provider["provider"], model["name"])
    return lookup


def synthesize(rank_models: List[dict], matcher: PriceMatcher) -> tuple[List[dict], List[dict]]:
    """Join ranked models with their prices; return the site records and one matching record per ranked model."""
    records, debug = [], []
    for model in rank_models:
        elo = int(model["Score"])
        if elo < MIN_ELO:
            continue
        price = matcher.find_match(model["Model"])
        debug.append({
            "rank_model": model["Model"],
            "matched_price_model": price.original_name if price else "No match found",
            "price": price.input_price if price else 0,
            "provider": price.provider if price else "N/A",
            "organization": model["organization"],
        })
        if price:
            records.append({
                "model": model["Model"],
                "elo": elo,
                "input_price": price.input_price,
                "output_price": price.output_price,
                "votes": int(model["Votes"]),
                "organization": model["organization"],
            })
    return records, debug


def main() -> None:
    rank_data = json.loads((DATA_DIR / "rank_data.json").read_text(encoding="utf-8"))
    print(f"  Loaded {len(rank_data['models'])} models from ranking data (updated: {rank_data['last_updated']})")
    price_lookup = load_price_lookup(json.loads((DATA_DIR / "price_data.json").read_text(encoding="utf-8")))
    print(f"  Loaded {len(price_lookup)} models from pricing data (updated: {date.today().isoformat()})")

    records, debug = synthesize(rank_data["models"], PriceMatcher(price_lookup))

    js_array = ",\n  ".join(json.dumps(record) for record in records)
    (DATA_DIR / "synthesized_data.js").write_text(
        f"export const data = [\n  {js_array}\n];\n\n"
        f'export const dataLastUpdated = "{rank_data["last_updated"]}";\n'
        f"export const minElo = {MIN_ELO};\n",
        encoding="utf-8",
    )
    (DATA_DIR / "price_matching_debug.json").write_text(json.dumps(debug, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Synthesized {len(records)} models, saved to data/synthesized_data.js")


if __name__ == "__main__":
    main()
