# Refresh the Pareto frontier

# Silly fetch - it is a ts file, but we only need the part after line 3 with a [ prepending it
rm ./data.js
touch data.js
echo "let mockData = [" >> ./data.js
curl -s https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator/resolve/main/src/lib/data.ts | tail -n +4 >> ./data.js
# add the lines below into data.json - as a new line
echo "console.log(JSON.stringify(mockData));" >> ./data.js
node ./data.js >> price_data.json
rm ./data.js

# Rank data is a bit harder, so bear with me... This is about to get ugly
