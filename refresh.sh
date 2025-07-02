#!/bin/bash

set -e

TMP_DOWNLOAD_FILE=$(mktemp)
TMP_JS_FILE=$(mktemp)
trap 'rm -f "$TMP_JS_FILE" "$TMP_DOWNLOAD_FILE"' EXIT # Remove temp files on exit

echo "🔄 Refreshing LM Arena Pareto frontier data..."

# ==============================================================================
# STEP 1: UPDATE PRICING DATA
# ==============================================================================
echo "📊 Fetching latest pricing data..."

PRICE_DATA_URL="https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator/resolve/main/src/lib/data.ts"

# Download the file, following redirects (-L)
echo "Downloading from $PRICE_DATA_URL..."
curl -sL "$PRICE_DATA_URL" -o "$TMP_DOWNLOAD_FILE"

# Check if download was successful
if [ ! -s "$TMP_DOWNLOAD_FILE" ]; then
    echo "❌ Failed to download pricing data from $PRICE_DATA_URL."
    echo "The downloaded file is empty. Please check the URL and your network connection."
    exit 1
fi
echo "Download successful."

# Process the downloaded file
echo "Processing downloaded data..."
# Use sed to transform the TypeScript file into executable JavaScript
sed -n '/export const mockData:.*= \[/,$p' "$TMP_DOWNLOAD_FILE" | \
    sed '1s/.*export const mockData:.*= \[/let mockData = \[/' > "$TMP_JS_FILE"

# Check if the processing was successful
if [ ! -s "$TMP_JS_FILE" ]; then
    echo "❌ Failed to process downloaded pricing data."
    echo "The structure of the source file at $PRICE_DATA_URL might have changed."
    echo "===== Downloaded content: ====="
    cat "$TMP_DOWNLOAD_FILE"
    echo "==============================="
    exit 1
fi
echo "Processing successful."

echo "console.log(JSON.stringify(mockData));" >> "$TMP_JS_FILE"
# Process the data and redirect output to price_data.json
node "$TMP_JS_FILE" | jq '.' > data/price_data.json

# ==============================================================================
# STEP 2: SCRAPE LATEST LM ARENA RANKING DATA
# ==============================================================================
echo "🏆 Scraping latest LM Arena rankings from lmarena.ai..."
python3 utils/extract_leaderboard.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to scrape LM Arena data. Please check the scraper script."
    exit 1
fi

# Verify the scraped data was created
if [ -f "data/rank_data.json" ]; then
    echo "✅ Successfully scraped and processed LM Arena data"
else
    echo "❌ rank_data.json not found after scraping. Please check the scraper output."
    exit 1
fi

# ==============================================================================
# STEP 3: GENERATE SYNTHESIZED DATA
# ==============================================================================
echo "🔧 Generating synthesized_data.js..."
python3 utils/generate_synthesized_data.py
if [ $? -ne 0 ]; then
    echo "❌ Data synthesis failed. Check generate_synthesized_data.py script"
    exit 1
else
    echo "✅ Data synthesis complete."
fi

# ==============================================================================
# STEP 4: UPDATE LAST UPDATED DATE IN HTML
# ==============================================================================
echo "📝 Updating HTML title..."
CURRENT_DATE=$(date +"%B %Y")
sed -i "s/Updated [A-Za-z]* [0-9]*/Updated $CURRENT_DATE/g" index.html

echo "✅ Data refresh complete!"