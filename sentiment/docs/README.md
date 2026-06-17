# 📂 Sentiment Analysis Module: Documentation & Reference Catalog

Welcome to the Sentiment Analysis module! This catalog serves as the central **Table of Contents (TOC)** and directory map for all documentation, tutorials, modular functions, APIs, prompts, and schema contracts available in this workspace.

---

## 🗺️ Workspace Map & Directory Structure

```
sentiment/
├── data/                    # Raw and cached sentiment datasets
├── docs/                    # Architectural guides, roadmaps, and standards
│   ├── architecture/        # Core & updated system designs
│   │   ├── macro_ingestion_architecture.md
│   │   ├── sentiment_analyzer_architecture.md
│   │   └── updated_architecture.md
│   ├── NEXT_STEPS.md
│   ├── docstring_standard.md
│   ├── news_providers.md
│   └── README.md            # This file
├── functions/               # Core codebase functions
│   ├── aggregator/          # News aggregation logic
│   ├── providers/           # API integrations for news platforms
│   ├── tools/               # Deterministic data/agent tools (edgar_tools, transcript_tools)
│   └── utils/               # Math, config, scheduler, and compliance logging utilities
├── logs/                    # Audit logs (scheduler_audit.jsonl, compliance_audit.jsonl)
├── prompts/                 # Core text prompts for agents (single-agent prompts, reading workers, scribe)
│   └── old/                 # Archived multi-agent prompts
├── schema_json/             # Validation JSON schemas for LLM outputs
├── scripts/                 # CLI scripts (news_sentiment_cli, macro_ingestion_cli)
│   └── multi-agent/         # Archived multi-agent scripts
└── tutorials/               # Step-by-step notebook guides and evolution
```

---

## 📄 Architectural Guides & Documentation

| Document File | Purpose / Description |
| :--- | :--- |
| [updated_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/architecture/updated_architecture.md) | **Updated System Design**: Details the full single-agent direct tool-calling architecture, the Smart Scheduler fail-safe layer, the Unstructured Reading Workers Layer, and the Thesis-CoT Audit Scribe compliance integration. |
| [sentiment_analyzer_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/architecture/sentiment_analyzer_architecture.md) | **Core System Design**: Explains the 3-layer system layout, mathematical scoring equations, database schemas, vector caching, and websocket contracts. |
| [macro_ingestion_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/architecture/macro_ingestion_architecture.md) | **Macro Ingestion Design**: Outlines the economic surprise index mathematical formulation, model interactions, data contracts, and fallback boundaries. |
| [news_providers.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/news_providers.md) | **API & Scraping Status**: Outlines support details for OpenBB platform news connectors, status matrix of the 11 integrated providers, and headless browser scraping results. |
| [NEXT_STEPS.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/NEXT_STEPS.md) | **Development Roadmap**: Details milestones, macro surprise ingestion API endpoints, Redis caching, SQLite storage layer, and the FinRL-X portfolio optimization Suggester. |
| [docstring_standard.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/docs/docstring_standard.md) | **Docstring Standard Guidelines**: Establishes strict rules for all Python functions and tools used by FinRobot agents, enforcing selection criteria, type hints, and error payloads. |

---

## 🚀 Tutorials: Agent & Refactoring Evolution

We transitioned from a rigid, monolithic notebook pipeline into a highly modular, decoupled, and agentic delegation architecture, and finally into a fast and reliable single-agent tool-calling framework:

### 1. [llama3_aapl_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_aapl_news.ipynb) — Monolithic Baseline (Tested ✅)
* **Purpose**: Fetches, cleans, and scores AAPL news articles inline.
* **Limitations**: Highly redundant inline cells, manual regex response sanitization, and lack of separation between concerns.

### 2. [llama3_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news.ipynb) — Modular Refactoring (Tested ✅)
* **Purpose**: Decouples the core pipeline functions from execution notebooks.
* **Key Enhancements**: Moving standard tasks to helper files (e.g., config generators, scrapers, database loaders) and wrapping them in standard agent factory creation methods.

### 3. [llama3_news_delegation.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news_delegation.ipynb) — Agent-to-Agent Nested Chat (Archived)
* **Purpose**: Setup AutoGen-based multi-agent coordination with transparent chunk batching.
* **Key Enhancements**: Used a User Proxy to delegate to a Senior Sentiment Analyst (CIO) Agent, which automatically delegated to a Sentiment Scorer Agent in batches. This has now been simplified to direct Python-orchestrated tool-calling for significantly faster execution and lower latency.

### 4. [macro_ingestion_delegation.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/macro_ingestion_delegation.ipynb) — Macro Ingestion & Multi-Agent Calculation (Archived)
* **Purpose**: Simulated macro indicators ingestion using MCP clients.
* **Key Enhancements**: Standardized shock index calculation. This has also been upgraded to a single-agent orchestrator with a deterministic `MacroScheduler` middleware layer to prevent rate limits and timeouts from failing the process.

---

## 💻 CLI Scripts & Utilities

### 1. [news_sentiment_cli.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/scripts/news_sentiment_cli.py)
* **Purpose**: Main single-agent command-line utility for executing the news sentiment analysis and portfolio weight adjustments. Now includes the Unstructured Reading Workers Layer (Risk Factors from SEC Edgar and Q&A Tension from FMP Transcripts) and a Thesis-CoT Scribe compliance gateway that logs weight overrides >15% to `logs/compliance_audit.jsonl`.
* **Usage**:
  ```bash
  python sentiment/scripts/news_sentiment_cli.py --ticker MSFT --limit 10
  ```

### 2. [macro_ingestion_cli.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/scripts/macro_ingestion_cli.py)
* **Purpose**: Main single-agent command-line utility for economic surprise index calculation. Implements the `MacroScheduler` fail-safe middleware and the `MacroSurpriseCalibrationAgent` standard deviation TTL cache.
* **Usage**:
  ```bash
  python sentiment/scripts/macro_ingestion_cli.py --event "CPI m/m" --indicator CPI
  ```

---

## 🛠️ Codebase Functions Reference

### 🌐 News Ingestion & Aggregation

#### 📂 Aggregator Component (`sentiment/functions/aggregator/`)
* **[fetch_aggregate_all_news](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/aggregator/aggregator.py#L17)**: Consolidates, deduplicates, and standardizes news articles from 11 sources.

#### 📂 Data Provider Endpoints (`sentiment/functions/providers/`)
* **[fetch_alpha_vantage](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/alpha_vantage.py#L5)**: Fetches news articles and sentiment metrics from the Alpha Vantage API.
* **[fetch_finviz_scrape](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/finviz.py#L39)**: Custom BeautifulSoup scraper parsing the public HTML news table on the Finviz page.
* **[fetch_nasdaq_api](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/nasdaq.py#L4)**: Fetches public news feeds from the Nasdaq JSON API endpoints.
* **[fetch_news_api](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/news_api.py#L5)**: Fetches news feed items from the official NewsAPI.org service.
* **[fetch_seeking_alpha_rapidapi](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/providers/seeking_alpha.py#L5)**: Fetches articles using the RapidAPI Tipsters Seeking Alpha API.

### 🔌 Structured Reading Workers & Ingestion Tools
* **[get_cik_by_ticker](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/edgar_tools.py)**: Resolves ticker symbols to official SEC CIK values using SEC mappings.
* **[get_10k_metadata_by_year](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/edgar_tools.py)**: Finds the accession numbers and primary documents for 10-K filings.
* **[extract_section_1a](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/edgar_tools.py)**: Deterministically extracts Item 1A (Risk Factors) from raw SEC text.
* **[extract_section_7](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/edgar_tools.py)**: Deterministically extracts Item 7 (MD&A) from raw SEC text.
* **[split_transcript](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/transcript_tools.py)**: Programmatically splits earnings call transcripts into Management Presentation vs. Analyst Q&A.

### 🏛️ Math, Fail-Safe, & Logging Utilities
Located in `sentiment/functions/utils/`:
* **[calculate_raw_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L3)**: Computes confidence-weighted average sentiment: $S_{\text{raw}} = \frac{\sum (s_i \cdot c_i)}{\sum c_i}$.
* **[calculate_macro_surprise](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L38)**: Evaluates economic surprise surprise scaled by impact tier weights: $\mathcal{S}_t = \omega \cdot \left| \frac{\text{Actual} - \text{Consensus}}{\sigma_{\text{historical}}} \right|$.
* **[calculate_effective_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L80)**: Adjusts sentiment score using asset beta and macro shocks: $\text{Effective Sentiment} = S_{\text{raw}} \cdot (1 + \beta_j \cdot \mathcal{S}_t)$.
* **[calculate_portfolio_sentiment](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L112)**: Aggregates ticker sentiment by portfolio weight: $\mathcal{S}_{\text{portfolio}} = \sum w_j \cdot \text{Effective Sentiment}_j$.
* **[normalize_weights](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py#L166)**: Normalizes top-K weights to sum to 1.0.
* **[MacroScheduler](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/scheduler.py)**: Failsafe state-machine wrapper that catches, classifies, and bypasses rate limits/timeouts using deterministic NaN-safe fallback payloads.
* **[MacroSurpriseCalibrationAgent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/calibration_agent.py)**: TTL cache wrapper for rolling standard deviation fetches with exponential backoff retries.
* **[log_scheduler_event](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/audit_logger.py)**: Writes scheduler events and error statuses to `logs/scheduler_audit.jsonl`.
* **[log_compliance_event](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/compliance_logger.py)**: Logs portfolio weight overrides to `logs/compliance_audit.jsonl`.

---

## 🤖 Agent Creators & Orchestration
* **[create_scorer_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/agents.py)**: Configures and returns the `Sentiment Scorer Agent` designed to parse individual articles.
* **[create_cio_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/agents.py)**: Configures and returns the `Senior Sentiment Analyst (CIO) Agent` which aggregates results and formats the final report.
* **[create_textual_inertia_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/agents.py)**: Kimi-powered agent that evaluates 10-K filing text to compute risk drift.
* **[create_tension_extractor_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/agents.py)**: Kimi-powered agent that analyzes earnings call transcripts Q&A for executive/analyst tension.
* **[create_scribe_agent](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/agents.py)**: The `Thesis-CoT Scribe` compliance agent that drafts justifications when portfolio weight adjustments exceed the 15% drift threshold.

---

## 📋 Prompts & Schema Contracts
* **[sentiment_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/sentiment_prompt.txt)**: Instructions for the Sentiment Scorer agent detailing how to score articles.
* **[cio_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/cio_prompt.txt)**: Instructions for the CIO agent detailing how to compile and validate the weighted average sentiment scores.
* **[chief_macro_economist_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/chief_macro_economist_prompt.txt)**: Single-agent instructions for the Chief Macro Economist coordinating agent.
* **[textual_inertia_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/textual_inertia_prompt.txt)**: Prompt for evaluating Risk Factors drift between filings.
* **[tension_extractor_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/tension_extractor_prompt.txt)**: Prompt for evaluating earnings call Q&A tension.
* **[scribe_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/scribe_prompt.txt)**: Prompt directing the Scribe agent to write compliance justification narratives.
