#!/bin/bash

set -e

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
# Use sed to transform the TypeScript file into executable JavaScript
sed -n '/export const mockData:.*= \[/,$p' "$TMP_DOWNLOAD_FILE" | \
    sed '1s/.*export const mockData:.*= \[/let mockData = \[/' > "$TMP_JS_FILE"

# Check if the processing was successful
if [ ! -s "$TMP_JS_FILE" ]; then
    echo "❌ Failed during pricing data conversion. Source format may have changed."
    cat "$TMP_DOWNLOAD_FILE"
    exit 1
fi
echo "${SUB}✅ Successfully fetched pricing data, saved to data/price_data.json"

echo "console.log(JSON.stringify(mockData));" >> "$TMP_JS_FILE"
# Process the data and redirect output to price_data.json
node "$TMP_JS_FILE" | jq '.' > data/price_data.json

# ==============================================================================
# STEP 2: SCRAPE LATEST LM ARENA RANKING DATA
# ==============================================================================
echo -e "\n🏆 Scraping latest LM Arena rankings from lmarena.ai..."
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