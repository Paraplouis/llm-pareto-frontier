#!/usr/bin/env python3
"""
LLM Pareto Frontier Data Generator

This script processes LLM Arena ranking data and pricing information to generate
a synthesized dataset for visualization. It includes intelligent model name matching,
fallback pricing estimation, and comprehensive error handling.

Author: LLM Pareto Frontier Project
Last Modified: 2024
"""

import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ModelData:
    """Data class for model information"""

    model: str
    elo: int
    price: float
    provider: str
    votes: int


@dataclass
class PriceInfo:
    """Data class for pricing information"""

    price: float
    provider: str
    original_name: str


@dataclass
class MatchingDebugInfo:
    """Data class for debugging price matching"""

    rank_model: str
    matched_price_model: str
    price: float
    provider: str


class ModelNameNormalizer:
    """Utility class for normalizing model names for better matching"""

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize model name for better matching"""
        name = name.lower()
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

    MODEL_FAMILIES = ["gemini", "gpt", "claude", "deepseek", "qwen", "grok"]

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

        for family in self.MODEL_FAMILIES:
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


class DefaultPricingEstimator:
    """Class for estimating default pricing based on model families"""

    PRICING_RULES = {
        "openai": {
            "patterns": [
                (r"4\.5|o3", 15.0, "Premium models"),
                (r"4o|4\.1", 2.5, "Standard GPT-4 models"),
                (r"mini|nano", 0.5, "Smaller models"),
            ],
            "default": 5.0,
            "provider": "OpenAI",
        },
        "anthropic": {
            "patterns": [
                (r"3\.7|opus", 15.0, "Premium Claude"),
                (r"sonnet", 3.0, "Standard Claude"),
                (r"haiku", 0.8, "Smaller Claude"),
            ],
            "default": 3.0,
            "provider": "Anthropic",
        },
        "google": {
            "patterns": [
                (r"2\.5.*pro", 1.25, "Gemini 2.5 Pro"),
                (r"pro", 1.25, "Pro models"),
                (r"flash", 0.15, "Flash models"),
            ],
            "default": 1.0,
            "provider": "Google",
        },
        "deepseek": {
            "patterns": [
                (r"v3", 0.27, "DeepSeek V3"),
                (r"r1", 0.55, "DeepSeek R1"),
            ],
            "default": 0.5,
            "provider": "DeepSeek",
        },
        "alibaba": {"patterns": [], "default": 0.9, "provider": "Alibaba"},
        "xai": {"patterns": [], "default": 2.0, "provider": "xAI"},
    }

    @classmethod
    def estimate_pricing(cls, model_name: str, organization: str) -> Tuple[float, str]:
        """Get default pricing for unknown models based on organization"""
        model_lower = model_name.lower()
        org_lower = organization.lower()

        # Determine provider family
        provider_family = cls._determine_provider_family(model_lower, org_lower)

        if provider_family in cls.PRICING_RULES:
            rules = cls.PRICING_RULES[provider_family]

            # Check pattern matches
            for pattern, price, description in rules["patterns"]:
                if re.search(pattern, model_lower):
                    logger.debug(
                        f"Matched pattern '{pattern}' for {model_name}: ${price} ({description})"
                    )
                    return price, rules["provider"]

            # Use default for provider
            return rules["default"], rules["provider"]

        # Fallback default
        return 1.0, organization or "Unknown"

    @classmethod
    def _determine_provider_family(
        cls, model_lower: str, org_lower: str
    ) -> Optional[str]:
        """Determine the provider family from model name and organization"""
        family_checks = [
            ("openai", ["gpt", "openai"]),
            ("anthropic", ["claude", "anthropic"]),
            ("google", ["gemini", "google"]),
            ("deepseek", ["deepseek"]),
            ("alibaba", ["qwen", "alibaba"]),
            ("xai", ["grok", "xai"]),
        ]

        for family, keywords in family_checks:
            if any(
                keyword in model_lower or keyword in org_lower for keyword in keywords
            ):
                return family

        return None


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
            rank_data = self._load_rank_data()
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
            self._save_results(synthesized_data, matching_debug)

            logger.info(
                f"✅ Generated synthesized_data.js with {len(synthesized_data)} models"
            )
            return synthesized_data

        except Exception as e:
            logger.error(f"❌ Failed to generate synthesized data: {e}")
            raise

    def _load_rank_data(self) -> List[Dict[str, Any]]:
        """Load ranking data from JSON file"""
        rank_file = self.data_dir / "rank_data.json"
        try:
            with open(rank_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"📊 Loaded {len(data)} models from ranking data")
            return data
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
                    price_lookup[model_name] = PriceInfo(
                        price=model["inputPrice"],
                        provider=provider_name,
                        original_name=model["name"],
                    )

            logger.info(f"💰 Loaded pricing data for {len(price_lookup)} models")
            return price_lookup

        except FileNotFoundError:
            raise FileNotFoundError(f"Price data file not found: {price_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in price data: {e}")

    def _process_model(
        self, model: Dict[str, Any], price_matcher: PriceMatcher
    ) -> Optional[Tuple[ModelData, MatchingDebugInfo]]:
        """Process a single model and return model data with debug info"""
        model_name = model["Model"]
        elo_score = model["Score"]
        votes = model["Votes"]

        # Find pricing information
        price_info = price_matcher.find_match(model_name)

        if price_info:
            if self.exclude_free and price_info.price <= 0:
                return None

            model_data = ModelData(
                model=model_name,
                elo=int(round(elo_score)),
                price=price_info.price,
                provider=price_info.provider,
                votes=votes
            )

            debug_info = MatchingDebugInfo(
                rank_model=model_name,
                matched_price_model=price_info.original_name,
                price=price_info.price,
                provider=price_info.provider,
            )
        else:
            # Use default pricing estimation
            organization = model.get("Organization", "Unknown")
            default_price, provider = DefaultPricingEstimator.estimate_pricing(
                model_name, organization
            )

            if self.exclude_free and default_price <= 0:
                return None

            model_data = ModelData(
                model=model_name, elo=int(round(elo_score)), price=default_price, provider=provider, votes=votes
            )

            debug_info = MatchingDebugInfo(
                rank_model=model_name,
                matched_price_model="DEFAULT_ESTIMATE",
                price=default_price,
                provider=provider,
            )

        return model_data, debug_info

    def _save_results(
        self, synthesized_data: List[ModelData], matching_debug: List[MatchingDebugInfo]
    ):
        """Save synthesized data and debug information"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate JavaScript file
        js_content = self._generate_js_content(synthesized_data, timestamp)

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
                }
                for debug in matching_debug
            ]
            json.dump(debug_data, f, indent=2, ensure_ascii=False)

        logger.info("💾 Saved synthesized data and debug information")

    def _generate_js_content(
        self, synthesized_data: List[ModelData], timestamp: str
    ) -> str:
        """Generate JavaScript content for the data file"""
        model_json_strings = [json.dumps(asdict(d), ensure_ascii=False) for d in synthesized_data]

        js_array = "[\n  " + ",\n  ".join(model_json_strings) + "\n]"

        js_content = f"export const data = {js_array};\n\n"

        js_content += f'export const dataLastUpdated = "{timestamp}";\n'

        return js_content


def main():
    """Main function to run the data synthesis"""
    try:
        synthesizer = DataSynthesizer(min_elo=1250, exclude_free=True)
        data = synthesizer.generate()

        print(f"\n✅ Successfully generated data for {len(data)} models")

    except Exception as e:
        logger.error(f"❌ Data synthesis failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())