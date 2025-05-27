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

# Step 2: Fetch latest LLM Arena ranking data
echo "🏆 Fetching latest LLM Arena rankings..."
# Try today's data first (since we run after 2 PM UTC, daily release should be available)
TODAY=$(date +%Y.%m.%d)
echo "Trying to fetch data for date: $TODAY"

# Try to download today's CSV from fboulnois/llm-leaderboard-csv
wget --no-check-certificate -O lmsys_latest.csv "https://github.com/fboulnois/llm-leaderboard-csv/releases/download/$TODAY/lmsys.csv" 2>/dev/null

# If today's data isn't available yet, try previous days
if [ ! -s lmsys_latest.csv ]; then
    echo "⚠️  Data for $TODAY not found, trying previous days..."
    for i in {1..7}; do
        DATE=$(date -d "$i days ago" +%Y.%m.%d)
        echo "Trying date: $DATE"
        wget --no-check-certificate -O lmsys_latest.csv "https://github.com/fboulnois/llm-leaderboard-csv/releases/download/$DATE/lmsys.csv" 2>/dev/null
        if [ -s lmsys_latest.csv ]; then
            echo "✅ Found data for $DATE"
            break
        fi
    done
fi

# Check if we got the data
if [ ! -s lmsys_latest.csv ]; then
    echo "❌ Failed to fetch LLM Arena data. Please check the repository manually."
    exit 1
fi

echo "✅ Successfully downloaded LLM Arena data ($(wc -l < lmsys_latest.csv) lines)"

# Step 3: Convert CSV to JSON format
echo "🔄 Converting CSV to JSON format..."
python3 scripts/convert_csv_to_json.py

# Step 4: Generate the synthesized_data.js file
echo "🔧 Generating synthesized_data.js..."
python3 scripts/generate_synthesized_data.py

# Step 5: Update the HTML title with current date
echo "📝 Updating HTML title..."
CURRENT_DATE=$(date +"%B %Y")
sed -i "s/Updated [A-Za-z]* [0-9]*/Updated $CURRENT_DATE/g" index.html

# Step 6: Clean up temporary files
echo "🧹 Cleaning up temporary files..."
rm -f lmsys_latest.csv

echo "✅ Data refresh complete!"
echo "📊 Website is ready at http://localhost:8000"
