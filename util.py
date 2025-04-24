# Install necessary library if you don't have it
# !pip install thefuzz python-Levenshtein

import re
from thefuzz import fuzz, process

# --- Data Definitions (Using a portion as requested) ---

# Dataset 1: Pricing Data
mockData = []
# Dataset 2: Ranking Data
rankData = []

# --- Helper Functions ---

def normalize_provider(name):
    """Normalizes provider/organization names for better matching."""
    if not name: return ""
    name = name.lower()
    name = name.replace(" ", "") # Remove spaces
    name = name.replace(".", "") # Remove dots (e.g., 01.ai -> 01ai)
    # Add specific known variations if needed
    if name == 'xAi': return 'xai'
    if name == '01Ai': return '01ai'
    if name == 'DeepSeek': return 'deepseek' # Correct typo
    return name

def normalize_model_name(name):
    """Normalizes model names for fuzzy matching."""
    if not name: return ""
    name = name.lower()
    # Remove common prefixes/suffixes often found in ranking data but not pricing
    name = re.sub(r'<path.*?>', '', name) # Remove SVG paths
    name = re.sub(r'<\w+.*?>', '', name) # Remove other potential HTML tags
    name = re.sub(r'-\d{4}-\d{2}-\d{2}', '', name) # Remove YYYY-MM-DD dates
    name = re.sub(r'-\d{6}', '', name) # Remove YYMMDD dates (e.g., 2407)
    name = re.sub(r'-\d{4}', '', name) # Remove YYYY dates or versions like 2501
    # Remove common terms that might differ or be absent

    # Specific replacements

    name = name.replace('latest', '') # chatgpt-4o -> gpt4o
    name = name.replace('chatgpt', 'gpt') # chatgpt-4o -> gpt4o
    name = name.replace('gpt ', 'gpt') # gpt-4o -> gpt4o
    name = name.replace('claude ', 'claude')
    name = name.replace('gemini ', 'gemini')
    name = name.replace('deepseek ', 'deepseek')
    name = name.replace('llama ', 'llama')
    name = name.replace('command ', 'command')
    name = name.replace('mistral ', 'mistral')
    name = name.replace('yi ', 'yi')
    name = name.replace('qwen ', 'qwen')

    # Remove parameter sizes (optional, might reduce accuracy if sizes differ)
    # name = re.sub(r'\s*\d+(\.\d+)?[bkmb]', '', name)
    name = re.sub(r'[-_/\s]+', ' ', name) # Replace separators with space

    return name.strip()


# --- Matching Logic ---

synthesized_data = []
PROVIDER_MATCH_THRESHOLD = 85 # Min score for provider name match
MODEL_MATCH_THRESHOLD = 80 # Min score for model name match

def main(mockData, rankData):

    # --- Precompute Pricing Data Lookup ---

    # Create a dictionary for faster lookup: {normalized_provider: {normalized_model_name: [original_model_info]}}
    pricing_lookup = {}
    for provider_info in mockData:
        original_provider_name = provider_info['provider']
        normalized_provider = normalize_provider(original_provider_name)
        if normalized_provider not in pricing_lookup:
            pricing_lookup[normalized_provider] = {}

        for model_info in provider_info['models']:
            original_model_name = model_info['name']
            normalized_model = normalize_model_name(original_model_name)
            if normalized_model not in pricing_lookup[normalized_provider]:
                pricing_lookup[normalized_provider][normalized_model] = []
            # Store original info along with normalized name for later use
            pricing_lookup[normalized_provider][normalized_model].append({
                **model_info,
                'original_provider': original_provider_name
            })

    # --- Matching Logic ---

    PROVIDER_MATCH_THRESHOLD = 75 # Min score for provider name match
    MODEL_MATCH_THRESHOLD = 60 # Min score for model name match

    for rank_item in rankData:
        rank_model_name = rank_item['Model']
        rank_org_name = rank_item['Organization']

        norm_rank_model = normalize_model_name(rank_model_name)
        norm_rank_org = normalize_provider(rank_org_name)

        best_match = None
        highest_score = -1

        # 1. Find potential matching providers
        # Use fuzzy matching for provider names
        provider_matches = process.extractBests(
            norm_rank_org,
            pricing_lookup.keys(),
            score_cutoff=PROVIDER_MATCH_THRESHOLD,
            scorer=fuzz.token_sort_ratio # Good for different word orders/typos
        )

        # If no provider matches, try a simpler ratio for cases like '01.ai' vs '01 ai'
        if not provider_matches:
            provider_matches = process.extractBests(
                norm_rank_org,
                pricing_lookup.keys(),
                score_cutoff=PROVIDER_MATCH_THRESHOLD,
                scorer=fuzz.ratio
            )

        # 2. For each matching provider, find potential matching models
        for matched_provider_norm, provider_score in provider_matches:
            if matched_provider_norm in pricing_lookup:
                # Get all normalized model names for this provider
                provider_model_names_norm = list(pricing_lookup[matched_provider_norm].keys())

                if not provider_model_names_norm:
                    continue

                # Use fuzzy matching for model names within the matched provider
                # Token sort ratio is often good for model names with version numbers etc.
                model_matches = process.extractBests(
                    norm_rank_model,
                    provider_model_names_norm,
                    score_cutoff=MODEL_MATCH_THRESHOLD,
                    scorer=fuzz.token_sort_ratio,
                    limit=5 # Check top 5 potential matches
                )

                # Refine model matching: consider partial ratio for substrings
                # and simple ratio for direct similarity
                refined_model_matches = []
                for model_norm, score_token_sort in model_matches:
                    score_partial = fuzz.partial_ratio(norm_rank_model, model_norm)
                    score_ratio = fuzz.ratio(norm_rank_model, model_norm)
                    # Combine scores (e.g., average or weighted average)
                    # Give higher weight to token_sort_ratio as it handles reordering well
                    combined_score = (score_token_sort * 0.6) + (score_partial * 0.2) + (score_ratio * 0.2)

                    # Also consider exact match on normalized names
                    if norm_rank_model == model_norm:
                        combined_score = 100 # Boost exact matches

                    if combined_score >= MODEL_MATCH_THRESHOLD:
                        refined_model_matches.append((model_norm, combined_score))

                # Sort refined matches by score
                refined_model_matches.sort(key=lambda x: x[1], reverse=True)

                if refined_model_matches:
                    best_model_norm, model_score = refined_model_matches[0]

                    # Calculate overall match score (e.g., average provider and model score)
                    overall_score = (provider_score + model_score) / 2

                    # If this match is better than the current best, update
                    if overall_score > highest_score:
                        # Retrieve the original model info (could be multiple if normalized names clash)
                        # For simplicity, take the first one. Could add logic to pick best original name match.
                        matched_model_info_list = pricing_lookup[matched_provider_norm][best_model_norm]
                        if matched_model_info_list:
                            best_model_data = matched_model_info_list[0]
                            highest_score = overall_score
                            best_match = {
                                'rank_data': rank_item,
                                'price_data': best_model_data,
                                'match_score_provider': provider_score,
                                'match_score_model': model_score,
                                'overall_match_score': overall_score,
                                'norm_rank_model': norm_rank_model,
                                'norm_price_model': best_model_norm,
                                'norm_rank_org': norm_rank_org,
                                'norm_price_org': matched_provider_norm
                            }

        # 3. Store the result (either matched or unmatched)
        if best_match:
            synthesized_data.append({
                'rank_model': rank_model_name,
                'rank_provider': rank_org_name,
                'rank_ub': rank_item.get('Rank (UB)'),
                'score': rank_item.get('Score'),
                'matched_price_model': best_match['price_data']['name'],
                'matched_price_provider': best_match['price_data']['original_provider'],
                'input_price': best_match['price_data']['inputPrice'],
                'output_price': best_match['price_data']['outputPrice'],
                'uri': best_match['price_data'].get('uri'), # Get URI if available
                'overall_match_score': round(best_match['overall_match_score'], 2),
                'provider_match_score': round(best_match['match_score_provider'], 2),
                'model_match_score': round(best_match['match_score_model'], 2),
                # Include normalized names for debugging/review
                # 'norm_rank_model': best_match['norm_rank_model'],
                # 'norm_price_model': best_match['norm_price_model'],
                # 'norm_rank_org': best_match['norm_rank_org'],
                # 'norm_price_org': best_match['norm_price_org'],
            })
        else:
            # Add unmatched items as well, indicating no price info found
            synthesized_data.append({
                'rank_model': rank_model_name,
                'rank_provider': rank_org_name,
                'rank_ub': rank_item.get('Rank (UB)'),
                'score': rank_item.get('Score'),
                'matched_price_model': None,
                'matched_price_provider': None,
                'input_price': None,
                'output_price': None,
                'uri': None,
                'overall_match_score': 0,
                'provider_match_score': 0,
                'model_match_score': 0,
            })


    # --- Output Results ---
    import json

    print(f"Successfully processed {len(rankData)} ranking entries.")
    print(f"Found price matches for {sum(1 for item in synthesized_data if item['matched_price_model'] is not None)} entries.")
    print("\n--- Synthesized Data (First 20 entries) ---")

    # Pretty print the first 20 results
    count = 0
    for item in synthesized_data:
        print(json.dumps(item, indent=2))
        count += 1
        if count >= 20:
            break

if __name__ == "__main__":
    # Parse two flags as mockData and rankData
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Process ranking data.')
    parser.add_argument('--priceData', action='store_true', help='Use mock data.')
    parser.add_argument('--rankData', action='store_true', help='Use rank data.')
    args = parser.parse_args()

    try:
        # Load mock data
        with open('./price_data.json', 'r') as f:
            mockData= json.load(f)
        with open('./rank_data.json', 'r') as f:
            rankData= json.load(f)
    except FileNotFoundError:
        print("Data file not found.")
        exit(1337)

    main(mockData, rankData)
