# LLM Arena Pareto Frontier

![llm-pareto-frontier](/screenshot.png)

A live visualization of the Pareto frontier for Large Language Models, showing the optimal performance-to-cost ratio based on LLM Arena rankings and current API pricing data.

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
   git clone https://github.com/your-username/llm-pareto-frontier.git
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

4. **Open `indew.html` in a browser**

## 🔄 Automated Updates

The project automatically updates daily via GitHub Actions:
- **Schedule**: Every day at 2 PM UTC
- **Process**: Fetches latest rankings and pricing, regenerates visualization data
- **Commit**: Automatically commits and pushes updates to the repository

## 📈 Data Sources

This project combines data from multiple sources:

- **LLM Rankings**: [LLM Arena Leaderboard](https://huggingface.co/spaces/lmarena-ai/chatbot-arena-leaderboard) via [fboulnois/llm-leaderboard-csv](https://github.com/fboulnois/llm-leaderboard-csv)
- **Pricing Data**: [LLM Pricing Calculator](https://huggingface.co/spaces/Presidentlin/llm-pricing-calculator) by Presidentlin & PhilSchmid

## 🤝 Contributing

Contributions are welcome! Areas where contributions would be particularly helpful:

- Adding more pricing data sources
- Improving the model name matching algorithm
- Enhancing the visualization with additional features
- Adding new filtering or analysis options

## 📝 License

This project is open source on MIT. 

Please check the individual data sources for their respective licenses:
- LLM Arena data: Check [LMSYS](https://lmsys.org/) licensing
- Pricing data: Check individual provider terms

## 🙏 Acknowledgments

Special thanks to:
- [LMSYS](https://lmsys.org/) and the LLM Arena team for comprehensive model rankings
- [Presidentlin](https://huggingface.co/Presidentlin) and [PhilSchmid](https://huggingface.co/philschmid) for the LLM pricing calculator
- [fboulnois](https://github.com/fboulnois) for maintaining CSV exports of LLM Arena data
- The open source community for tools and libraries

*Data automatically updated daily at 2 PM UTC*
