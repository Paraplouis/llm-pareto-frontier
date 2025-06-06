# LLM Arena Pareto Frontier

![llm-pareto-frontier](/screenshot.png)
> Screenshot of the Pareto frontier visualization on 27/05/2025

## 📊 What is the Pareto Frontier?

The Pareto frontier shows models that are "Pareto optimal" - meaning no other model offers better performance at a lower price. These are the models you should consider when choosing an LLM based on performance and cost efficiency.

Available at https://paraplouis.github.io/llm-pareto-frontier/

## 🔄 Automated Updates

The project automatically updates data daily via GitHub Actions at 2 PM UTC.

### 🛠️ Usage

Python dependencies for data processing and scraping:
```bash
pip install -r requirements.txt
```

To run the project locally, run:
```bash
python -m http.server
```
and open http://localhost:8000 in your browser.

## 🏗️ Code structure

```
├── index.html                      # Main entry point
├── styles.css                      # Application styles & responsive design
├── requirements.txt                # Python dependencies for data processing & scraping
├── refresh.sh                      # Manual refresh script for data updates
├── screenshot.png                  # Project screenshot for documentation
├── .github/
│   └── workflows/
│       ├── daily-refresh.yml       # Automated daily data refresh via GitHub Actions
│       └── deploy-pages.yml        # GitHub Pages deployment configuration
├── data/
│   ├── synthesized_data.js         # Final LLM model data (auto-updated)
│   ├── rank_data.json              # Raw ranking data from LLM Arena
│   └── price_data.json             # Raw pricing data
├── utils/
│   ├── extract_leaderboard.py      # Web scraper for LLM Arena rankings (using Hugging Face API)
│   └── generate_synthesized_data.py # Main data processing & synthesis utility
└── js/
    ├── loader.js                   # Dynamic module loader with global namespace
    ├── app.js                      # Main application orchestrator
    └── modules/
        ├── dataProcessor.js        # Data filtering & Pareto frontier calculations
        ├── chartRenderer.js        # D3.js chart rendering & interactions
        └── uiController.js         # UI controls & user interface management
```

## 🤝 Contributing

Contributions are welcome! I'm interested in evolving this project in these directions:

- **Enforce data reliability**: more pricing data sources and better model name matching
- **Real price estimation**: implement formulas to estimate actual costs beyond static input pricing
- **Filtering** by parameter count (total/active), open-source status, ...
- **Multi-dimensional frontiers** across different performance metrics
- **Historical animations** of frontier evolution over time
- **Extended data integration** from all Chatbot Arena tabs to enable domain-specific frontiers and richer analysis

## 🙏 Acknowledgements

This project builds upon the work of several projects. Special thanks to:

- The **LMSYS team** for creating and maintaining the [LLM Arena Leaderboard](https://lmarena.ai/leaderboard/text/overall).
- **Lincoln Gachagua** for his work on the [LLM Pricing Calculator](https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator) based on **Philipp Schmid**'s [original version](https://huggingface.co/spaces/philschmid/llm-pricing-calculator).
- **Winston Bosan** for the [original implementation](https://github.com/winston-bosan/llm-pareto-frontier) that inspired me to continue the project.