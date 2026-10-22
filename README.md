[![Refresh data and deploy Pages](https://github.com/Paraplouis/llm-pareto-frontier/actions/workflows/daily-refresh.yml/badge.svg)](https://github.com/Paraplouis/llm-pareto-frontier/actions/workflows/daily-refresh.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Paraplouis/llm-pareto-frontier)

# LLM Pareto frontier

![llm-pareto-frontier](/screenshot.png)

The chart plots each model's LM Arena ELO score against its OpenRouter API price. A model is on the Pareto frontier when no other model is both cheaper and better ranked; the stepped line shows the best score available at each price.

Site: https://paraplouis.github.io/llm-pareto-frontier/

## Data and updates

- Rankings come from the official LM Arena Hugging Face dataset (text, style control); prices come from the OpenRouter models API.
- A ranked model gets a price only from an OpenRouter entry naming the same model: family, tier, and version must agree, and sizes must agree when both names give one. Models no longer listed on OpenRouter are left out. `PRICE_MODEL_OVERRIDES` in `utils/generate_synthesized_data.py` lists the few names that need an explicit match.
- GitHub Actions refreshes the data every day at 14:17 UTC, commits changed files in `data/` to `main`, and deploys the site in the same run. Pushes that change `data/**` also deploy.

## Local use

The refresh scripts need only `curl` and the Python standard library.

```bash
./refresh.sh             # fetch prices and rankings, regenerate data/
python -m http.server    # serve the site at http://localhost:8000
```

Tests:

```bash
python -m pytest
node --test tests/test_dataProcessor.mjs
node tests/test_browser.mjs   # needs Puppeteer, Google Chrome, and the local server
```

## Code structure

```
├── index.html, styles.css            # Page and styles
├── fonts/                            # Newsreader and IBM Plex Mono (SIL Open Font License)
├── js/
│   ├── app.js                        # Filter state; re-renders on change
│   ├── modules/
│   │   ├── dataProcessor.js          # Price blending, Pareto frontier, search
│   │   ├── chartRenderer.js          # D3 scatter plot and hover
│   │   └── uiController.js           # Controls, frontier list, table, tooltip
│   └── vendor/d3.v7.min.js
├── data/
│   ├── synthesized_data.js           # Ranked models with prices, read by the site
│   └── price_data.json               # OpenRouter prices per author
├── utils/
│   ├── extract_leaderboard.py        # LM Arena rankings from Hugging Face
│   ├── generate_openrouter_price_data.py
│   └── generate_synthesized_data.py  # Joins rankings and prices
├── refresh.sh
└── tests/
```

## Ideas

- Filter by parameter count or open-weight status.
- Frontiers for other LM Arena categories.
- Animate how the frontier moves over time.

## Acknowledgements

- The LM Arena team for the [leaderboard](https://lmarena.ai/leaderboard/text/overall) and its [dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset).
- OpenRouter for publishing model prices through its public models API.
- Winston Bosan for the [original implementation](https://github.com/winston-bosan/llm-pareto-frontier).
