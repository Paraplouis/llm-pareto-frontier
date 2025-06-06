#!/bin/bash
# Refresh the Pareto frontier with latest data

echo "🔄 Refreshing LLM Arena Pareto Frontier data..."

# Step 1: Update pricing data
echo "📊 Fetching latest pricing data..."
rm -f ./data.js
touch data.js
echo "let mockData = [" >> ./data.js
curl -s https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator/resolve/main/src/lib/data.ts | tail -n +4 >> ./data.js
echo "console.log(JSON.stringify(mockData));" >> ./data.js
node ./data.js | jq '.' > data/price_data.json
rm -f ./data.js

# Step 2: Scrape latest LLM Arena ranking data from the new interface
echo "🏆 Scraping latest LLM Arena rankings from lmarena.ai..."
python3 utils/extract_leaderboard.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to scrape LLM Arena data. Please check the scraper script."
    exit 1
fi

# Verify the scraped data was created
if [ -f "data/rank_data.json" ]; then
    echo "✅ Successfully scraped and processed LLM Arena data"
else
    echo "❌ rank_data.json not found after scraping. Please check the scraper output."
    exit 1
fi

# Step 3: Generate the synthesized_data.js file
echo "🔧 Generating synthesized_data.js..."
python3 utils/generate_synthesized_data.py

# Step 4: Update the HTML title with current date
echo "📝 Updating HTML title..."
CURRENT_DATE=$(date +"%B %Y")
sed -i "s/Updated [A-Za-z]* [0-9]*/Updated $CURRENT_DATE/g" index.html

# Step 5: Clean up temporary files
echo "🧹 Cleaning up temporary files..."
# No temporary files to clean up with the new scraper

echo "✅ Data refresh complete!"