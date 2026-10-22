#!/bin/bash
# Refresh data/price_data.json, data/rank_data.json and data/synthesized_data.js from OpenRouter and LM Arena.
set -euo pipefail
cd "$(dirname "$0")"

echo "Fetching OpenRouter pricing"
curl --silent --show-error --fail --location --max-time 30 https://openrouter.ai/api/v1/models -o data/openrouter_raw.json
python3 utils/generate_openrouter_price_data.py data/openrouter_raw.json

echo "Fetching LM Arena rankings"
python3 utils/extract_leaderboard.py

echo "Synthesizing data"
python3 utils/generate_synthesized_data.py

echo "Data refresh complete"
