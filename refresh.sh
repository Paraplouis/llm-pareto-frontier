#!/bin/bash

set -e
set -o pipefail

TMP_DOWNLOAD_FILE=$(mktemp)
TMP_JS_FILE=$(mktemp)
trap 'rm -f "$TMP_JS_FILE" "$TMP_DOWNLOAD_FILE"' EXIT # Remove temp files on exit

# ANSI color codes for styling
GREEN_BOLD="\033[1;92m"
RESET="\033[0m"

# ==============================================================================
# STEP 1: UPDATE PRICING DATA
# ==============================================================================
echo "📊 Fetching latest pricing data..."

PRICE_DATA_URL="https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator/resolve/main/src/lib/data.ts"

SUB="  " # two-space indent for sub-steps

echo "${SUB}↳ Downloading pricing data from LLM Pricing Calculator Space on Hugging Face..."
curl -sL "$PRICE_DATA_URL" -o "$TMP_DOWNLOAD_FILE"

# Check if download was successful
if [ ! -s "$TMP_DOWNLOAD_FILE" ]; then
    echo "❌ Failed: downloaded file is empty. Check the URL or network connection."
    exit 1
fi

# Process the downloaded file
echo "${SUB}↳ Converting TypeScript to JSON..."
# Prefer extracting only the mockData array region to avoid ESM imports
sed -n '/export const mockData:.*= \[/,$p' "$TMP_DOWNLOAD_FILE" | \
    sed '1s/.*export const mockData:.*= \[/let mockData = \[/' > "$TMP_JS_FILE"

# Validate extraction
if [ ! -s "$TMP_JS_FILE" ]; then
    echo "❌ Failed during pricing data conversion. Source format may have changed."
    cat "$TMP_DOWNLOAD_FILE"
    exit 1
fi

echo "console.log(JSON.stringify(mockData));" >> "$TMP_JS_FILE"

# Produce JSON (jq also validates)
node "$TMP_JS_FILE" | jq -e '.' > data/price_data.json

# Final guard to ensure file was written
if [ ! -s "data/price_data.json" ]; then
    echo "❌ price_data.json is empty after conversion."
    exit 1
fi

echo "${SUB}✅ Successfully fetched pricing data, saved to data/price_data.json"

# ==============================================================================
# STEP 2: SCRAPE LATEST LM ARENA RANKING DATA
# ==============================================================================
echo -e "\n🏆 Scraping latest LM Arena rankings from lmarena.ai (manual)..."
command -v node >/dev/null 2>&1 || { echo "❌ node is required for price data conversion"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "❌ jq is required for price data conversion"; exit 1; }
python3 utils/extract_leaderboard.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to scrape LM Arena data. Please check the scraper script."
    exit 1
fi

# Verify the scraped data was created
if [ ! -f "data/rank_data.json" ]; then
    echo "❌ rank_data.json not found after scraping. Please check the scraper output."
    exit 1
fi

# ==============================================================================
# STEP 3: GENERATE SYNTHESIZED DATA
# ==============================================================================
echo -e "\n🔧 Generating synthesized data..."
python3 utils/generate_synthesized_data.py
if [ $? -ne 0 ]; then
    echo "❌ Data synthesis failed. Check generate_synthesized_data.py script"
    exit 1
fi

# ==============================================================================
# STEP 4: UPDATE LAST UPDATED DATE IN HTML
# ==============================================================================
echo -e "\n📝 Updating HTML title..."
CURRENT_DATE=$(date +"%B %Y")
sed -i "s/Updated [A-Za-z]* [0-9]*/Updated $CURRENT_DATE/g" index.html

echo -e "\n${GREEN_BOLD}✅ DATA REFRESH COMPLETE!${RESET}"