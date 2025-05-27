#!/usr/bin/env python3
import json
import re

def normalize_model_name(name):
    """Normalize model name for better matching"""
    # Convert to lowercase and remove common variations
    name = name.lower()
    # Remove version dates and preview indicators
    name = re.sub(r'-\d{4}-\d{2}-\d{2}', '', name)
    name = re.sub(r'-\d{2}-\d{2}', '', name)
    name = re.sub(r'preview.*', '', name)
    name = re.sub(r'exp.*', '', name)
    name = re.sub(r'latest.*', '', name)
    # Normalize separators
    name = re.sub(r'[-_\s]+', ' ', name).strip()
    return name

def find_price_match(model_name, price_lookup):
    """Find the best price match for a model name with improved logic"""
    model_lower = model_name.lower()
    model_normalized = normalize_model_name(model_name)
    
    # Direct match first
    if model_lower in price_lookup:
        return price_lookup[model_lower]
    
    # Try normalized match
    for price_model, info in price_lookup.items():
        if normalize_model_name(price_model) == model_normalized:
            return info
    
    # Enhanced fuzzy matching with better scoring
    best_match = None
    best_score = 0
    
    for price_model, info in price_lookup.items():
        # Extract key parts of model names for comparison
        model_parts = set(re.findall(r'\w+', model_normalized))
        price_parts = set(re.findall(r'\w+', normalize_model_name(price_model)))
        
        # Calculate overlap score
        overlap = len(model_parts & price_parts)
        total_parts = len(model_parts | price_parts)
        
        if overlap >= 2 and total_parts > 0:  # At least 2 words must match
            # Calculate similarity ratio
            similarity = overlap / total_parts
            
            # Bonus for exact model family matches
            bonus = 0
            if any(part in price_model.lower() for part in ['gemini', 'gpt', 'claude', 'deepseek']):
                model_family = None
                for family in ['gemini', 'gpt', 'claude', 'deepseek']:
                    if family in model_lower:
                        model_family = family
                        break
                
                if model_family and model_family in price_model.lower():
                    bonus += 0.3
                    
                    # Additional bonus for version matching (e.g., 2.5, 4.0, etc.)
                    model_version = re.search(r'(\d+\.?\d*)', model_lower)
                    price_version = re.search(r'(\d+\.?\d*)', price_model.lower())
                    if model_version and price_version and model_version.group(1) == price_version.group(1):
                        bonus += 0.2
            
            final_score = similarity + bonus
            
            if final_score > best_score:
                best_score = final_score
                best_match = info
    
    return best_match

def get_default_pricing(model_name, organization):
    """Get default pricing for unknown models based on organization with more accurate estimates"""
    default_price = 1.0
    
    model_lower = model_name.lower()
    org_lower = organization.lower()
    
    if 'gpt' in model_lower or 'openai' in org_lower:
        if '4.5' in model_lower or 'o3' in model_lower:
            default_price = 15.0  # Premium models
        elif '4o' in model_lower or '4.1' in model_lower:
            default_price = 2.5   # Standard GPT-4 models
        elif 'mini' in model_lower or 'nano' in model_lower:
            default_price = 0.5   # Smaller models
        else:
            default_price = 5.0   # Default OpenAI
        organization = "OpenAI"
        
    elif 'claude' in model_lower or 'anthropic' in org_lower:
        if '3.7' in model_lower or 'opus' in model_lower:
            default_price = 15.0  # Premium Claude
        elif 'sonnet' in model_lower:
            default_price = 3.0   # Standard Claude
        elif 'haiku' in model_lower:
            default_price = 0.8   # Smaller Claude
        else:
            default_price = 3.0   # Default Anthropic
        organization = "Anthropic"
        
    elif 'gemini' in model_lower or 'google' in org_lower:
        if '2.5' in model_lower and 'pro' in model_lower:
            default_price = 1.25  # Gemini 2.5 Pro (200K context)
        elif 'pro' in model_lower:
            default_price = 1.25  # Other Pro models
        elif 'flash' in model_lower:
            default_price = 0.15  # Flash models
        else:
            default_price = 1.0   # Default Google
        organization = "Google"
        
    elif 'deepseek' in model_lower:
        if 'v3' in model_lower:
            default_price = 0.27  # DeepSeek V3
        elif 'r1' in model_lower:
            default_price = 0.55  # DeepSeek R1
        else:
            default_price = 0.5   # Default DeepSeek
        organization = "DeepSeek"
        
    elif 'qwen' in model_lower or 'alibaba' in org_lower:
        default_price = 0.9
        organization = "Alibaba"
        
    elif 'grok' in model_lower or 'xai' in org_lower:
        default_price = 2.0
        organization = "xAI"
    
    return default_price, organization

def generate_synthesized_data():
    """Generate synthesized_data.js from rank and price data"""
    # Read the updated rank data
    with open('data/rank_data.json', 'r', encoding='utf-8') as f:
        rank_data = json.load(f)

    # Read the pricing data
    with open('data/price_data.json', 'r', encoding='utf-8') as f:
        price_data = json.load(f)

    # Create a mapping of model names to pricing info
    price_lookup = {}
    for provider in price_data:
        provider_name = provider['provider']
        for model in provider['models']:
            model_name = model['name'].lower()
            # Use input price as the main price point
            price_lookup[model_name] = {
                'price': model['inputPrice'],
                'provider': provider_name,
                'original_name': model['name']  # Keep original for debugging
            }

    # Generate the synthesized data
    synthesized_data = []
    matching_debug = []  # For debugging price matches
    
    for model in rank_data:  # Filter by ELO score instead of rank limit
        if model['Score'] < 1250:  # Skip models with ELO below 1250
            continue
        model_name = model['Model']
        elo_score = model['Score']
        
        # Find pricing information
        price_info = find_price_match(model_name, price_lookup)
        
        if price_info:
            # Skip free models (price = 0) as they're likely self-hosted, not API
            if price_info['price'] > 0:
                synthesized_data.append({
                    'model': model_name,
                    'elo': elo_score,
                    'price': price_info['price'],
                    'provider': price_info['provider']
                })
                matching_debug.append({
                    'rank_model': model_name,
                    'matched_price_model': price_info['original_name'],
                    'price': price_info['price'],
                    'provider': price_info['provider']
                })
        else:
            # Try to guess provider from organization field
            organization = model.get('Organization', 'Unknown')
            default_price, provider = get_default_pricing(model_name, organization)
            
            # Skip free models (price = 0) as they're likely self-hosted, not API
            if default_price > 0:
                synthesized_data.append({
                    'model': model_name,
                    'elo': elo_score,
                    'price': default_price,
                    'provider': provider
                })
                matching_debug.append({
                    'rank_model': model_name,
                    'matched_price_model': 'DEFAULT_ESTIMATE',
                    'price': default_price,
                    'provider': provider
                })

    # Generate the JavaScript file with timestamp
    from datetime import datetime
    update_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    js_content = f"""// LLM model data - Updated from LLM Arena leaderboard
// Last updated: {update_timestamp}
const dataLastUpdated = "{update_timestamp}";
const data = [
"""

    for model in synthesized_data:
        js_content += f'  {{ model: "{model["model"]}", elo: {model["elo"]}, price: {model["price"]}, provider: "{model["provider"]}" }},\n'

    js_content += "];\n"

    # Write the JavaScript file
    with open('data/synthesized_data.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    # Write debug information
    with open('data/price_matching_debug.json', 'w', encoding='utf-8') as f:
        json.dump(matching_debug, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated synthesized_data.js with {len(synthesized_data)} models")
    print("💡 Price matching debug info saved to price_matching_debug.json")
    return synthesized_data

if __name__ == "__main__":
    data = generate_synthesized_data()
    print("📊 Top 5 models:")
    for i, model in enumerate(data[:5]):
        print(f"{i+1}. {model['model']} - ELO: {model['elo']}, Price: ${model['price']}") 