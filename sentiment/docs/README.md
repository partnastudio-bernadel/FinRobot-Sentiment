# 📂 Sentiment Analysis Module: Documentation & Reference Catalog

Welcome to the Sentiment Analysis module! This catalog serves as the central **Table of Contents (TOC)** and directory map for all documentation, tutorials, modular functions, APIs, prompts, and schema contracts available in this workspace.

---

## 🗺️ Workspace Map & Directory Structure

```
sentiment/
├── data/                    # Raw and cached sentiment datasets
├── docs/                    # Architectural guides and roadmaps (including this README.md)
│   ├── NEXT_STEPS.md
│   ├── news_providers.md
│   └── sentiment_analyzer_architecture.md
├── functions/               # Core codebase functions (scrapers, API providers, formulas, agents)
│   ├── aggregator/          # Aggregation logic to fetch news across multiple sources
│   ├── providers/           # API integrations for specific news platforms
│   ├── tools/               # Agent creation and execution tools
│   └── utils/               # Math, scraper, and config helper files
├── prompts/                 # Core text prompt templates for agents
├── schema_json/             # Validation JSON schemas for LLM outputs
└── tutorials/               # Step-by-step evolution notebook guides
```

---

## 📄 Architectural Guides & Documentation

| Document File | Purpose / Description |
| :--- | :--- |
| [sentiment_analyzer_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/sentiment_analyzer_architecture.md) | **Core System Design**: Explains the 3-layer system layout, 2-agent sequential sequence flow, mathematical scoring equations, app and IntentCore database schemas, vector caching, and websocket payload contracts. |
| [news_providers.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/news_providers.md) | **API & Scraping Status**: Outlines support details for OpenBB platform news connectors, status matrix of the 11 integrated providers, and headless browser scraping results across major news domains. |
| [NEXT_STEPS.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/NEXT_STEPS.md) | **Development Roadmap**: Details current progress on mathematical formulas, macro data ingestion framework, dual-source inputs (ForexFactory + Alpha Vantage), and future RL portfolio rebalancing milestones. |

---

## 🚀 Tutorials: Agent & Refactoring Evolution

We transitioned from a rigid, monolithic notebook pipeline into a highly modular, decoupled, and agentic delegation architecture. You can follow this evolutionary path via these tutorials:

### 1. [llama3_aapl_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_aapl_news.ipynb) — Monolithic Baseline (Tested ✅)
* **Purpose**: Fetches, cleans, and scores AAPL news articles inline.
* **Limitations**: Highly redundant inline cells, manual regex response sanitization, hardcoded FAISS database setup, and lack of separation between concerns.

### 2. [llama3_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news.ipynb) — Modular Refactoring (Tested ✅)
* **Purpose**: Decouples the core pipeline functions from execution notebooks.
* **Key Enhancements**: Moving standard tasks to helper files (e.g. LLM configuration generators, custom scrapers, database loaders) and wrapping them in standard agent factory creation methods.

### 3. [llama3_news_delegation.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news_delegation.ipynb) — Agent-to-Agent Nested Chat (Still Testing ⚠️)
* **Purpose**: Sets up AutoGen-based multi-agent coordination.
* **Key Enhancements**: Instead of orchestrating step-by-step code execution in Python, the pipeline configures a direct delegation chat structure where a User Proxy chats with a **Senior Sentiment Analyst (CIO) Agent**, which automatically triggers a **Sentiment Scorer Agent** via an AutoGen **Nested Chat**.

---

## 🛠️ Codebase Functions Reference

All reusable functions are organized logically within the `sentiment/functions` package:

### 🌐 News Ingestion & Aggregation

#### 📂 Aggregator Component
Located in `sentiment/functions/aggregator/`:
* **[fetch_aggregate_all_news](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/aggregator/aggregator.py#L17)**
  * **Signature**: `fetch_aggregate_all_news(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Consolidates, deduplicates, and standardizes news articles from 11 sources (including OpenBB endpoints and custom API scraper integrations).

#### 📂 Data Provider Endpoints
Located in `sentiment/functions/providers/`:
* **[fetch_alpha_vantage](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/alpha_vantage.py#L5)**
  * **Signature**: `fetch_alpha_vantage(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Fetches news articles and sentiment metrics from the Alpha Vantage News & Sentiment API.
* **[fetch_finviz_scrape](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/finviz.py#L39)**
  * **Signature**: `fetch_finviz_scrape(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Custom BeautifulSoup scraper that parses the public HTML news table on the Finviz stock page.
* **[parse_finviz_date](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/finviz.py#L6)**
  * **Signature**: `parse_finviz_date(date_list: list) -> pd.Timestamp`
  * **Description**: Utility to parse finviz-specific scraped date lists (e.g. `["today", "04:15PM"]`) into standard timestamps.
* **[fetch_nasdaq_api](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/nasdaq.py#L4)**
  * **Signature**: `fetch_nasdaq_api(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Fetches public news feeds from the Nasdaq JSON API endpoints.
* **[fetch_news_api](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/news_api.py#L5)**
  * **Signature**: `fetch_news_api(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Fetches news feed items from the official NewsAPI.org service.
* **[fetch_seeking_alpha_rapidapi](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/seeking_alpha.py#L5)**
  * **Signature**: `fetch_seeking_alpha_rapidapi(symbol: str = "AAPL", limit: int = 100) -> pd.DataFrame`
  * **Description**: Fetches articles using the RapidAPI Tipsters Seeking Alpha API (historical wrapper).

---

### 🏛️ Math & Helper Utilities
Located in `sentiment/functions/utils/`:

* **[calculate_raw_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L3)**
  * **Signature**: `calculate_raw_sentiment(articles: List[Dict[str, Any]]) -> float`
  * **Description**: Computes confidence-weighted average sentiment: $S_{\text{raw}} = \frac{\sum (s_i \cdot c_i)}{\sum c_i}$.
* **[calculate_macro_surprise](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L38)**
  * **Signature**: `calculate_macro_surprise(actual: float, consensus: float, historical_std: float, tier: str) -> Tuple[float, bool]`
  * **Description**: Evaluates economic surprise surprise scaled by impact tier weights: $\mathcal{S}_t = \omega \cdot \left| \frac{\text{Actual} - \text{Consensus}}{\sigma_{\text{historical}}} \right|$.
* **[calculate_effective_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L80)**
  * **Signature**: `calculate_effective_sentiment(ticker: str, raw_sentiment: float, macro_shock: float, custom_beta: Optional[float] = None) -> float`
  * **Description**: Adjusts sentiment score using asset beta and macro shocks: $\text{Effective Sentiment} = S_{\text{raw}} \cdot (1 + \beta_j \cdot \mathcal{S}_t)$.
* **[calculate_portfolio_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L112)**
  * **Signature**: `calculate_portfolio_sentiment(weights: Dict[str, float], effective_sentiments: Dict[str, float]) -> float`
  * **Description**: Aggregates ticker sentiment by portfolio weight: $\mathcal{S}_{\text{portfolio}} = \sum w_j \cdot \text{Effective Sentiment}_j$.
* **[calculate_portfolio_drift](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L140)**
  * **Signature**: `calculate_portfolio_drift(actual_weights: Dict[str, float], target_weights: Dict[str, float]) -> float`
  * **Description**: Computes active asset allocation drift: $\text{Drift}_t = \sum |w_{\text{actual}, j} - w_{\text{target}, j}|$.
* **[build_vector_store](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/build.py#L5)**
  * **Signature**: `build_vector_store(csv_path, embeddings, limit_rows=300)`
  * **Description**: Indexes historical financial sentiment datasets into a FAISS local vector database to provide few-shot calibration examples.
* **[fetch_article_text](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/scraper.py#L4)**
  * **Signature**: `fetch_article_text(url: str, timeout_ms: int = 15000) -> str`
  * **Description**: Headless browser automation utilizing Playwright Chromium to extract full paragraph body texts.
* **[standardize_df](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/standardizer.py#L3)**
  * **Signature**: `standardize_df(df: pd.DataFrame, provider_name: str) -> pd.DataFrame`
  * **Description**: Standardizes columns, timezones, and structure of fetched article dataframes.
* **[generate_config](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/config.py#L1)**
  * **Signature**: `generate_config(model_name, api_endpoint, api_key, max_tokens=2048)`
  * **Description**: Sets up the model config structure required by FinRobot/AutoGen.
* **[read_file_content](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/read_and_clean.py#L2)**
  * **Signature**: `read_file_content(file_path)`
  * **Description**: Simple helper to read prompt text or json schemas.
* **[extract_and_clean_response](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/read_and_clean.py#L7)**
  * **Signature**: `extract_and_clean_response(user_proxy, agent, is_json=False)`
  * **Description**: Cleans LLM output tags and strips terminal flags from chat logs.

---

### 🤖 Agent Creators & Orchestration
Located in `sentiment/functions/tools/`:

* **[create_scorer_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/agents.py#L4)**
  * **Signature**: `create_scorer_agent(prompt_path, schema_path, llm_config)`
  * **Description**: Configures and returns the `Sentiment Scorer Agent` designed to parse individual articles.
* **[create_cio_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/agents.py#L24)**
  * **Signature**: `create_cio_agent(prompt_path, schema_path, output_schema_path, scored_articles_path, llm_config)`
  * **Description**: Configures and returns the `Senior Sentiment Analyst (CIO) Agent` which aggregates results and formats the final report.
* **[custom_nested_chat_reply](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/custom_reply.py#L3)**
  * **Signature**: `custom_nested_chat_reply(chat_queue, recipient, messages, sender, config)`
  * **Description**: Custom registration callback that handles standard AutoGen agent-to-agent delegation messaging.
* **[prepare_articles](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/prepare_articles.py#L3)**
  * **Signature**: `prepare_articles(df_news, db, limit=5, k_examples=2)`
  * **Description**: Filters raw news articles, retrieves semantic neighbors from the FAISS database, and returns standard prompt-ready structures.

---

## 📋 Prompts & Schema Contracts

The agent workflows enforce strict input/output formats through files located in the `prompts/` and `schema_json/` folders:

### 💬 System Prompts
* **[sentiment_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/sentiment_prompt.txt)**: Instructions for the Sentiment Scorer agent detailing how to score articles against target schema contracts.
* **[cio_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/cio_prompt.txt)**: Instructions for the CIO agent detailing how to compile and validate the weighted average sentiment scores.

### 📐 JSON Output Schemas
* **[sentiment_schema.json](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/schema_json/sentiment_schema.json)**: Schema mapping individual article scoring outputs.
* **[scorer_schema.json](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/schema_json/scorer_schema.json)**: Constraint definition schema for LLM tools.
* **[cio_output_schema.json](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/schema_json/cio_output_schema.json)**: Standard schema validation for the CIO agent's final report.
* **[cio_scored_articles.json](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/schema_json/cio_scored_articles.json)**: Input schema format for article feeds processed by the CIO.


