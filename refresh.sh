#!/bin/bash

set -e
set -o pipefail

# ANSI color codes for styling
GREEN_BOLD="\033[1;92m"
RESET="\033[0m"

# ==============================================================================
# PRE-FLIGHT: CHECK DEPENDENCIES
# ==============================================================================
command -v curl >/dev/null 2>&1 || { echo "❌ curl is required for data refresh"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 is required for data extraction and synthesis"; exit 1; }

PYTHON3="${BASH_SOURCE%/*}/.venv/bin/python3"
if [ ! -f "$PYTHON3" ]; then
    PYTHON3="python3"
fi

# ==============================================================================
# STEP 1: UPDATE OPENROUTER PRICING DATA
# ==============================================================================
echo "📊 Fetching latest OpenRouter pricing data..."

SUB="  " # two-space indent for sub-steps
OPENROUTER_URL="https://openrouter.ai/api/v1/models"
OPENROUTER_FILE="data/openrouter_raw.json"

echo "${SUB}↳ Downloading model data from OpenRouter API..."
if ! curl -sL --max-time 30 "$OPENROUTER_URL" -o "$OPENROUTER_FILE" || [ ! -s "$OPENROUTER_FILE" ]; then
    echo "❌ OpenRouter download failed."
    exit 1
fi
$PYTHON3 utils/generate_openrouter_price_data.py "$OPENROUTER_FILE"

# ==============================================================================
# STEP 2: FETCH LATEST LM ARENA RANKING DATA
# ==============================================================================
echo -e "\n🏆 Fetching latest LM Arena rankings from Hugging Face..."
$PYTHON3 utils/extract_leaderboard.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to fetch LM Arena data. Please check the extraction script."
    exit 1
fi

if [ ! -f "data/rank_data.json" ]; then
    echo "❌ rank_data.json not found after extraction. Please check the script output."
    exit 1
fi

# ==============================================================================
# STEP 3: GENERATE SYNTHESIZED DATA
# ==============================================================================
echo -e "\n🔧 Generating synthesized data..."
$PYTHON3 utils/generate_synthesized_data.py
if [ $? -ne 0 ]; then
    echo "❌ Data synthesis failed. Check generate_synthesized_data.py script"
    exit 1
fi

echo -e "\n${GREEN_BOLD}✅ DATA REFRESH COMPLETE!${RESET}"
