import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import date, datetime
from collections import Counter, defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------------
# Data classes
# ------------------------------

@dataclass
class ModelData:
    """Data class for synthesized model information including token pricing"""

    model: str
    elo: int
    input_price: float
    output_price: float
    cheapest_provider: str
    votes: int
    matched_price_model: str
    organization: str

@dataclass
class PriceInfo:
    """Data class for pricing information with separate input/output rates"""

    input_price: float
    output_price: float
    provider: str
    original_name: str


@dataclass
class MatchingDebugInfo:
    """Data class for debugging price matching"""

    rank_model: str
    matched_price_model: str
    price: float
    provider: str
    organization: str


class ModelNameNormalizer:
    """Utility class for normalizing model names for better matching"""

    SPECIAL_CASES = {
        r'\bchatgpt-4o\b': 'gpt-4o',
    }

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize model name for better matching"""
        name = name.lower()

        for pattern, replacement in ModelNameNormalizer.SPECIAL_CASES.items():
            name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)

        # Remove version dates and preview indicators more robustly
        name = re.sub(r"-\d{4}-\d{2}-\d{2}|-\d{4,}", "", name)
        name = re.sub(r"-\d{2}-\d{2}", "", name)
        name = re.sub(r"preview.*|exp.*|latest.*|beta.*|v\d.*", "", name)
        
        # Remove quality/quantization indicators
        name = re.sub(r"-bf16|-fp\d+|-instruct|-chat", "", name)
        
        # Standardize model size indicators
        name = re.sub(r"(\d+)b-", r"\1b ", name)

        # Normalize separators
        name = re.sub(r"[-_\s]+", " ", name).strip()
        return name


class PriceMatcher:
    """Class responsible for matching model names with pricing data"""

    def __init__(self, price_lookup: Dict[str, PriceInfo]):
        self.price_lookup = price_lookup

    def find_match(self, model_name: str) -> Optional[PriceInfo]:
        """Find the best price match for a model name with improved logic"""
        model_lower = model_name.lower()
        model_normalized = ModelNameNormalizer.normalize(model_name)

        # Direct match first
        if model_lower in self.price_lookup:
            return self.price_lookup[model_lower]

        # Try normalized match
        for price_model, info in self.price_lookup.items():
            if ModelNameNormalizer.normalize(price_model) == model_normalized:
                return info

        # Enhanced fuzzy matching with better scoring
        return self._fuzzy_match(model_lower, model_normalized)

    def _fuzzy_match(
        self, model_lower: str, model_normalized: str
    ) -> Optional[PriceInfo]:
        """Perform fuzzy matching with scoring"""
        best_match = None
        best_score = 0

        for price_model, info in self.price_lookup.items():
            score = self._calculate_similarity_score(
                model_lower, model_normalized, price_model
            )

            if score > best_score:
                best_score = score
                best_match = info

        return best_match if best_score > 0.5 else None  # Minimum threshold

    def _calculate_similarity_score(
        self, model_lower: str, model_normalized: str, price_model: str
    ) -> float:
        """Calculate similarity score between model names"""
        model_parts = set(re.findall(r"\w+", model_normalized))
        price_parts = set(
            re.findall(r"\w+", ModelNameNormalizer.normalize(price_model))
        )

        overlap = len(model_parts & price_parts)
        total_parts = len(model_parts | price_parts)

        if overlap < 2 or total_parts == 0:
            return 0

        # Base similarity ratio
        similarity = overlap / total_parts

        # Family matching bonus
        family_bonus = self._calculate_family_bonus(model_lower, price_model.lower())

        return similarity + family_bonus

    def _calculate_family_bonus(
        self, model_lower: str, price_model_lower: str
    ) -> float:
        """Calculate bonus for model family matches"""
        bonus = 0

        for family in ModelNameFormatter.MODEL_FAMILIES:
            if family in model_lower and family in price_model_lower:
                bonus += 0.3

                # Version matching bonus
                model_version = re.search(r"(\d+\.?\d*)", model_lower)
                price_version = re.search(r"(\d+\.?\d*)", price_model_lower)
                if (
                    model_version
                    and price_version
                    and model_version.group(1) == price_version.group(1)
                ):
                    bonus += 0.2
                break

        return bonus


class ModelNameFormatter:
    """Formats model names for display using dynamic rules."""

    ACRONYMS = {"ai", "dpo", "gpu", "it", "llm", "moe", "eu", "uk", "us", "vqa"}  # Removed 'claude'
    MODEL_FAMILIES = ["claude", "codellama", "command", "deepseek", "gemma", "gemini", "gpt", "grok", "llama", "mistral", "mixtral", "qwen"]

    @staticmethod
    def format_name(name: str, file_date: str) -> str:
        """
        Dynamically formats a model name using rules for capitalization, dates, and families.
        """
        # Normalize and split into words
        normalized = ModelNameNormalizer.normalize(name)
        words = re.split(r'[\s_-]+', normalized)

        # Capitalize intelligently
        formatted_words = []
        for word in words:
            if word.lower() in ModelNameFormatter.ACRONYMS:
                formatted_words.append(word.upper())
            elif word.lower() in ModelNameFormatter.MODEL_FAMILIES:
                formatted_words.append(word.capitalize())
            elif re.match(r'\d+(\.\d+)?', word):  # Versions like 3.1
                formatted_words.append(word)
            else:
                formatted_words.append(word.capitalize())

        formatted_name = " ".join(formatted_words)

        # Improved date handling: detect YYYYMMDD or partial dates
        import datetime
        current_year = datetime.date.today().year
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', name)  # For YYYYMMDD
        if date_match:
            year, month, day = date_match.groups()
            formatted_name += f" ({year}-{month}-{day})"
        else:
            partial_date = re.search(r'(\d{2})(\d{2})', name)  # For MMDD, prepend current year
            if partial_date:
                month, day = partial_date.groups()
                formatted_name += f" ({current_year}-{month}-{day})"

        # Special handling for previews/betas
        if "preview" in name.lower():
            formatted_name += " Preview"
        elif "beta" in name.lower():
            formatted_name += " beta"

        return formatted_name


class DataSynthesizer:
    """Main class for synthesizing LLM data"""

    def __init__(self, min_elo: int = 1250, exclude_free: bool = True):
        self.min_elo = min_elo
        self.exclude_free = exclude_free
        # Make data_dir relative to this script's parent directory
        self.script_dir = Path(__file__).resolve().parent
        self.data_dir = self.script_dir.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True) # Ensure data directory exists

    def generate(self) -> List[ModelData]:
        """Generate synthesized data from rank and price data"""
        try:
            # Load data
            rank_data, last_updated = self._load_rank_data()
            price_lookup = self._load_price_data()

            # Initialize components
            price_matcher = PriceMatcher(price_lookup)

            # Process data
            synthesized_data = []
            matching_debug = []

            for model in rank_data:
                if model["Score"] < self.min_elo:
                    continue

                result = self._process_model(model, price_matcher)
                if result:
                    model_data, debug_info = result
                    synthesized_data.append(model_data)
                    matching_debug.append(debug_info)

            # Save results
            self._save_results(synthesized_data, matching_debug, last_updated)

            return synthesized_data

        except Exception as e:
            logger.error(f"❌ Failed to generate synthesized data: {e}")
            raise

    def _load_rank_data(self) -> Tuple[List[Dict[str, Any]], str]:
        """Load ranking data from JSON file"""
        rank_file = self.data_dir / "rank_data.json"
        try:
            with open(rank_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            last_updated = data.get("last_updated")
            models = data.get("models", [])
            
            logger.info(f"  ↳ Loaded {len(models)} models from ranking data (updated: {last_updated})")
            return models, last_updated
        except FileNotFoundError:
            raise FileNotFoundError(f"Ranking data file not found: {rank_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in ranking data: {e}")

    def _load_price_data(self) -> Dict[str, PriceInfo]:
        """Load pricing data and create lookup dictionary"""
        price_file = self.data_dir / "price_data.json"
        try:
            with open(price_file, "r", encoding="utf-8") as f:
                price_data = json.load(f)

            price_lookup = {}
            for provider in price_data:
                provider_name = provider["provider"]
                for model in provider["models"]:
                    model_name = model["name"].lower()
                    current_price = model["inputPrice"]

                    # If model already exists, keep the one with the lower price
                    if (
                        model_name not in price_lookup
                        or current_price < price_lookup[model_name].input_price
                    ):
                        price_lookup[model_name] = PriceInfo(
                            input_price=current_price,
                            output_price=model.get("outputPrice", current_price),
                            provider=provider_name,
                            original_name=model["name"],
                        )

            logger.info(f"  ↳ Loaded {len(price_lookup)} models from pricing data (updated: {date.today().strftime("%Y-%m-%d")})")
            return price_lookup

        except FileNotFoundError:
            raise FileNotFoundError(f"Price data file not found: {price_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in price data: {e}")

    def _process_model(
        self, model: Dict[str, Any], price_matcher: PriceMatcher
    ) -> Optional[Tuple[ModelData, MatchingDebugInfo]]:
        """
        Processes a single model record.
        It normalizes the model name, finds a price match, and returns
        structured data for the model and for debugging.
        """
        model_name = model["Model"]
        elo = int(model["Score"])
        votes = model.get("Votes", 0)
        organization = model.get("organization", "Unknown")

        # Skip model if below min_elo
        if elo < self.min_elo:
            return None

        # Format model name for display
        file_date = model.get("file_date", "")
        formatted_name = ModelNameFormatter.format_name(model_name, file_date)

        # Attempt to find a price match
        price_info = price_matcher.find_match(model_name)

        if price_info:
            if self.exclude_free and price_info.input_price == 0:
                return None  # Skip free models if excluded

            model_data = ModelData(
                model=formatted_name,
                elo=elo,
                input_price=price_info.input_price,
                output_price=price_info.output_price,
                cheapest_provider=price_info.provider,
                votes=votes,
                matched_price_model=price_info.original_name,
                organization=organization
            )
            debug_info = MatchingDebugInfo(
                rank_model=model_name,
                matched_price_model=price_info.original_name,
                price=price_info.input_price,
                provider=price_info.provider,
                organization=organization
            )
            return model_data, debug_info

        # New: Skip if no real match found
            return None

    def _save_results(
        self, synthesized_data: List[ModelData], matching_debug: List[MatchingDebugInfo], timestamp: str
    ):
        """Save synthesized data and debug information"""
        # Generate JavaScript file
        js_content = self._generate_js_content(
            synthesized_data, timestamp, self.min_elo, self.exclude_free
        )

        # Save files
        with open(self.data_dir / "synthesized_data.js", "w", encoding="utf-8") as f:
            f.write(js_content)

        with open(
            self.data_dir / "price_matching_debug.json", "w", encoding="utf-8"
        ) as f:
            debug_data = [
                {
                    "rank_model": debug.rank_model,
                    "matched_price_model": debug.matched_price_model,
                    "price": debug.price,
                    "provider": debug.provider,
                    "organization": debug.organization,
                }
                for debug in matching_debug
            ]
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        logger.info("  ↳ Created debug and synthesized data files")

    def _generate_js_content(
        self,
        synthesized_data: List[ModelData],
        timestamp: str,
        min_elo: int,
        exclude_free: bool,
    ) -> str:
        """Generate JavaScript file content"""
        
        # Pretty-print JSON for readability
        records = []
        for item in synthesized_data:
            records.append(
                {
                    "model": item.model,
                    "elo": item.elo,
                    "input_price": item.input_price,
                    "output_price": item.output_price,
                    "cheapest_provider": item.cheapest_provider,
                    "votes": item.votes,
                    "organization": item.organization
                }
            )

        js_array = ",\n  ".join([json.dumps(record) for record in records])
        js_content = f"""export const data = [\n  {js_array}\n];

export const dataLastUpdated = "{timestamp}";
export const minElo = {min_elo};
export const excludeFree = {'true' if exclude_free else 'false'};
"""
        return js_content


def main():
    """Main function to run the data synthesis"""
    try:
        synthesizer = DataSynthesizer(min_elo=1000, exclude_free=True)
        data = synthesizer.generate()

        print(f"  ✅ Successfully synthesized data for {len(data)} models, saved to data/synthesized_data.js")

    except Exception as e:
        logger.error(f"❌ Data synthesis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())