# LLM Arena Pareto Frontier

![llm-pareto-frontier](/screenshot.png)
> Screenshot of the Pareto frontier visualization on 27/05/2025

## 📊 What is the Pareto Frontier?

The Pareto frontier shows models that are "Pareto optimal" - meaning no other model offers better performance at a lower price. These are the models you should consider when choosing an LLM based on performance and cost efficiency.

## 🛠️ Setup

### Prerequisites
- Python 3.x
- Node.js (for processing pricing data)
- `jq` (for JSON formatting)
- A web browser

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Paraplouis/llm-pareto-frontier.git
   cd llm-pareto-frontier
   ```

2. **Make the refresh script executable**
   ```bash
   chmod +x refresh.sh
   ```

3. **Update data**
   ```bash
   ./refresh.sh
   ```

4. **Open `index.html` in a browser**

## 🔄 Automated Updates

The project automatically updates daily via GitHub Actions:
- **Schedule**: Every day at 2 PM UTC
- **Process**: Fetches latest rankings and pricing, regenerates visualization data
- **Commit**: Automatically commits and pushes updates to the repository

## 📈 Data Sources

This project combines data from multiple sources:

- **LLM Rankings**: [LLM Arena Leaderboard](https://huggingface.co/spaces/lmarena-ai/chatbot-arena-leaderboard) via [fboulnois/llm-leaderboard-csv](https://github.com/fboulnois/llm-leaderboard-csv) by [fboulnois](https://github.com/fboulnois)
- **Pricing Data**: [LLM Pricing Calculator](https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator) by [Lincoln Gachagua](https://huggingface.co/Presidentlin) based on [PhilSchmid/llm-pricing-calculator](https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator) by [Philipp Schmid](https://huggingface.co/philschmid)

## 🤝 Contributing

Contributions are welcome! I'm interested in evolving this project in these directions:

- **Enforce data reliability**: more pricing data sources and better model name matching
- **Real price estimation**: implement formulas to estimate actual costs beyond static input pricing
- **Historical animations** of frontier evolution over time
- **Filtering** by parameter count (total/active), open-source status, ...
- **Multi-dimensional frontiers** across different performance metrics
- **Extended data integration** from all Chatbot Arena tabs to enable domain-specific frontiers and richer analysis

*Thanks to [Winston Bosan](https://github.com/winston-bosan) for it's original implementation !*