# 💻 CLI Scripts & Integration Reference Catalog

This directory contains standalone Command Line Interface (CLI) scripts designed for executing agent-based analysis pipelines, calculating metrics, and orchestrating Model Context Protocol (MCP) clients.

Both CLI utilities expose programmatically exportable orchestrator functions, making them ready for integration with background task schedulers (e.g. Celery), API routing layers (e.g. FastAPI), or cron configurations.

---

## 1. 📰 Stock News Sentiment Analyzer (`news_sentiment_cli.py`)

A multi-agent sentiment compilation utility that fetches recent stock news from 11 distinct sources (including OpenBB endpoints), retrieves semantic calibration examples from a local vector database, and delegates scoring tasks to scorer agents in transparent batches.

### Command Line Flags:
| Flag | Long Flag | Parameter Type | Default Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-t` | `--ticker` | `string` | `"AAPL"` | The stock ticker symbol to retrieve news and analyze sentiment for. |
| `-l` | `--limit` | `integer` | `5` | Maximum number of retrieved articles to batch and score. |
| `-c` | `--csv` | `string` | `data/financial_sentiment.csv` | Path to the historical financial sentiment CSV used to build the FAISS vector calibration database. |
| `-e` | `--env` | `string` | `.env.local` | Path to the environment configuration file containing API keys and model parameters. |

### CLI Usage Example:
```bash
# Run sentiment analysis for AAPL fetching and scoring the top 10 articles
python sentiment/scripts/news_sentiment_cli.py --ticker AAPL --limit 10

# Custom configuration file and custom calibration data path
python sentiment/scripts/news_sentiment_cli.py -t MSFT -l 5 -e .env -c data/custom_calibration.csv
```

---

## 2. 📈 Macro Economic Ingestion & Surprise Index CLI (`macro_ingestion_cli.py`)

An MCP-enabled surprise index orchestrator. It queries the local ForexFactory scraper MCP client to harvest current economic event releases (Actual vs. Forecast) and calls the remote Alpha Vantage MCP server to query baseline rolling standard deviations, automatically calculating a standardized shock index $\mathcal{S}_t$.

### Command Line Flags:
| Flag | Long Flag | Parameter Type | Default Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-v` | `--event` | `string` | `"CPI m/m"` | Target ForexFactory economic calendar event name to search (case-insensitive substring filter, e.g. `"CPI m/m"`, `"Core CPI m/m"`). |
| `-i` | `--indicator` | `string` | `"CPI"` | Macro indicator identifier matching Alpha Vantage API metrics (used for calculating the rolling baseline standard deviation). |
| `-e` | `--env` | `string` | `.env.local` | Path to the environment configuration file containing API keys and local scraper timeout variables. |

### CLI Usage Example:
```bash
# Retrieve USD CPI calendar event and baseline indicator values for this month
python sentiment/scripts/macro_ingestion_cli.py --event "CPI m/m" --indicator CPI

# Custom environment file and searching for Core CPI
python sentiment/scripts/macro_ingestion_cli.py -v "Core CPI m/m" -i CPI -e .env.local
```

---

## 🔌 API & Python Import Workflows
Both scripts are architected around clean, decoupled core functions. You can import their execution controllers directly into your backend routing layers without invoking shell subprocesses.

```python
# Import the news sentiment orchestrator
from scripts.news_sentiment_cli import run_sentiment_analysis

result = run_sentiment_analysis(ticker="AAPL", limit=5)
print(f"Weighted average sentiment: {result['metrics']['average_sentiment']}")

# Import the macro ingestion orchestrator
from scripts.macro_ingestion_cli import run_macro_ingestion

macro_report = run_macro_ingestion(event_name="CPI m/m", indicator_name="CPI")
print(f"Calculated surprise index S_t: {macro_report['metrics']['macro_surprise_score']}")
```
