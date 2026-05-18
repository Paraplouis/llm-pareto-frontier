[![Deploy Pages on data changes](https://github.com/Paraplouis/llm-pareto-frontier/actions/workflows/daily-refresh.yml/badge.svg)](https://github.com/Paraplouis/llm-pareto-frontier/actions/workflows/daily-refresh.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Paraplouis/llm-pareto-frontier)

# LLM Pareto frontier

![llm-pareto-frontier](/screenshot.png)
> Screenshot of the Pareto frontier visualization on 27/05/2025

## 📊 What is the Pareto Frontier?

The Pareto frontier shows models that are "Pareto optimal" - meaning no other model offers better performance at a lower price. These are the models you should consider when choosing an LLM based on performance and cost efficiency.

Available at https://paraplouis.github.io/llm-pareto-frontier/

## 🔄 Updates and Deployment

- Data refresh is manual: run `./refresh.sh` locally and commit the updated files in `data/`. Rankings come from the official LM Arena Hugging Face dataset; pricing comes from OpenRouter.
- GitHub Pages deploys automatically on pushes that change files under `data/**`.

### 🛠️ Usage

The refresh scripts use `curl` and the Python standard library; no Python package install is required.

To run the project locally, run:
```bash
python -m http.server
```
and open http://localhost:8000 in your browser.

## 🏗️ Code structure

```
├── index.html                      # Main entry point
├── styles.css                      # Application styles & responsive design
├── refresh.sh                      # Manual refresh script for data updates
├── screenshot.png                  # Project screenshot for documentation
├── .github/
│   └── workflows/
│       └── daily-refresh.yml       # Deploy Pages on data/** changes
├── data/
│   ├── synthesized_data.js         # Final LLM model data (auto-updated)
│   ├── rank_data.json              # Raw ranking data from LM Arena
│   └── price_data.json             # Raw pricing data
├── utils/
│   ├── extract_leaderboard.py      # Fetches LM Arena rankings from Hugging Face dataset server
│   ├── generate_openrouter_price_data.py # Generates pricing data from OpenRouter
│   └── generate_synthesized_data.py # Main data processing & synthesis utility
└── js/
    ├── app.js                      # Main application orchestrator
    └── modules/
        ├── dataProcessor.js        # Data filtering & Pareto frontier calculations
        ├── chartRenderer.js        # D3.js chart rendering & interactions
        └── uiController.js         # UI controls & user interface management
```

## 🤝 Contributing

Contributions are welcome! I'm interested in evolving this project in these directions:

- **Enforce data reliability**: better OpenRouter matching and model name normalization
- **Real price estimation**: implement formulas to estimate actual costs beyond static input pricing
- **Filtering** by parameter count (total/active), open-source status, ...
- **Multi-dimensional frontiers** across different performance metrics
- **Historical animations** of frontier evolution over time
- **Extended data integration** from all Chatbot Arena tabs to enable domain-specific frontiers and richer analysis

## 🙏 Acknowledgements

This project builds upon the work of several projects. Special thanks to:

- The **LM Arena team** for creating and maintaining the [LM Arena Leaderboard](https://lmarena.ai/leaderboard/text/overall) and official [leaderboard dataset](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset).
- **OpenRouter** for publishing model pricing through its public models API.
- **Winston Bosan** for the [original implementation](https://github.com/winston-bosan/llm-pareto-frontier) that inspired me to continue the project.
