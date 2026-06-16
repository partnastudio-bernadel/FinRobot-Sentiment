# SentinelAlpha: Development Roadmap & Next Steps

This document outlines the roadmap for the **Sentiment Alpha & Rebalancing Pipeline**, documenting what has been implemented so far and detailing the immediate next steps to link sentiment signals with portfolio governance.

---

## 🏛️ Completed: Step 1 — Mathematical Formulas (Signal Adjustment)

We have successfully implemented and verified the core mathematical equations from Section 2 of the [TRD](file:///d:/PartnaStudio/sentinel/baseline/TRD.md).

* **Module**: [formulas.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/formulas.py)
* **Tests**: [test_formulas.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/test_formulas.py)

### Implemented Functions:
1. **Confidence-Weighted Raw Sentiment ($S_{\text{raw}}$)**:
   $$S_{\text{raw}, j, t} = \frac{\sum_{i=1}^{M_j} s_{i} \cdot c_{i}}{\sum_{i=1}^{M_j} c_{i}}$$
   * *Logic*: Defaults to `0.0` (Neutral) if the article list is empty.
2. **Macro Severity Surprise Index ($\mathcal{S}_t$)**:
   $$\mathcal{S}_t = \omega_{\text{static}} \times \left| \frac{\text{Actual}_t - \text{Consensus}_t}{\sigma_{\text{historical}}} \right|$$
   * *Logic*: Defaults standard deviation to `1.0` if missing or zero (preventing division-by-zero), and triggers a boolean warning flag.
3. **Effective Ticker Sentiment**:
   $$\text{Effective Sentiment}_{j, t} = S_{\text{raw}, j, t} \times (1 + \beta_j \cdot \mathcal{S}_t)$$
   * *Logic*: Scales raw sentiment using default sector betas (e.g. `AAPL`: 1.2, `MSFT`: 1.1) or accepts an optional custom beta.
4. **Portfolio Sentiment**:
   $$\mathcal{S}_{\text{portfolio}, t} = \sum_{j=1}^{n} w_{j, t} \times \text{Effective Sentiment}_{j, t}$$
5. **Portfolio Drift ($L1$-Norm Deviation)**:
   $$\text{Drift}_t = \sum_{j=1}^{n} |w_{\text{actual}, j, t} - w_{\text{target}, j, t}|$$

---

## 🔌 Step 2: Macro Ingestion Strategy (Dual-Source Pipeline)

To fully decouple data harvesting and ensure high-availability calculations for the `calculate_macro_surprise` module, the ingestion layer requires a dual-source infrastructure strategy combining an asynchronous scraper framework with Model Context Protocol (MCP) servers.

### 1. Ingestion Architecture
```
[ForexFactory Web Scraper] ──► Real-Time Core Calendar Feeds (Actual vs. Consensus) ┐
                                                                                   ├──► [FastAPI Data Worker] ──► calculate_macro_surprise()
[Alpha Vantage MCP Server] ──► Historical Multi-Year Baseline (Rolling Std Dev σ)   ┘
```

#### Alpha Vantage MCP Server Integration
* **Strategic Role**: Acts as the primary data engine for long-horizon mathematical context, populating the rolling historical standard deviation ($\sigma_{\text{historical}}$) via standardized payloads.
* **Implementation Details**: Connects as a remote execution layer directly into your FinRobot multi-agent pipeline (https://mcp.alphavantage.co/mcp). This eliminates custom API rate-limiting loops when calculating standard deviations across commodity pricing, currency benchmarks, and multi-year macroeconomic data grids.

#### ForexFactory Scraper Wire-In
* **Strategic Role**: Supplies real-time high-impact macro data releases (Actual, Consensus, and Impact Tier labels) for intraday dynamic tilts.
* **Implementation Details**: Implemented within the FinRobot cluster utilizing asynchronous residential proxy cycling to scrape daily event details. This pulls upcoming high-impact economic calendar streams (e.g., Non-Farm Payrolls, CPI prints) and parses event tiers ("red", "orange", "yellow") directly into the `tier_weights` dictionary.

### 2. Technical Fallback Workflows (TRD Compliance)
To handle data exceptions cleanly, the system maps connections across both sources to avoid structural downtime:
* **Scraper Block Policy**: If the ForexFactory scraper hits a sustained network ban or HTTP 403/429 block lasting over 1 hour, the pipeline logs a `stale_calendar_flag`. It automatically routes requests through the OpenBB Core API or default macro indices to keep operations running smoothly.
* **Missing Denominator Safeguard**: If Alpha Vantage tracking drops out during a live calculation—causing $\sigma_{\text{historical}}$ to return as `None` or `0.0`—the calculation layer triggers the code’s inner catch block:
  ```python
  std_denominator = 1.0
  warning_flag = True
  ```
  This zeroes out custom scaling parameters cleanly and falls back directly to the core baseline portfolio allocation ($w_t = w^{\text{base}}_t$), preventing application crashes.

### 3. Next Engineering Sprint Milestones
* **Expose Ingestion Endpoints**: Create dedicated endpoints within the database configuration (`POST /v1/ingest/macro-calendar`) to wire real-time text arrays directly into `calculate_macro_surprise`.
* **Setup Redis TTL Caching**: Implement active caching on computed surprise metrics within Redis, utilizing dynamic Time-To-Live (TTL) horizons tailored around scheduled global release calendars to minimize processing overhead.

---

## 💾 Step 3: Establish the Storage Layer (AppDB)

To connect the agent outputs to the user interface, we must set up the **AppDB** schema contracts described in [sentiment_analyzer_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/sentiment_analyzer_architecture.md#L106-L111).

### Action Items:
1. **Create SQLite/Postgres Tables**:
   * **`articles`**: Tracks individual article scores, confidences, sources, and reasoning summaries.
   * **`intraday_velocity`**: Tracks ticker, hourly timestamp, and aggregate sentiment velocity.
   * **`sentiment_leaderboard`**: Compiles compound scores and 30-day percentage changes.
2. **Post-Processing Database Handler**:
   * Write a Python database connector script (`sentiment/functions/utils/db_handler.py`).
   * Hook the final JSON output of the CIO Agent (`final_report_msg`) into this script to parse, compute mathematical metrics (from Step 1), and save them immediately to the database.
3. **Trigger Ingestion on live run**:
   * Tie this handler to the FastAPI worker endpoints to make sure the user interface receives updates.

---

## 🤖 Step 4: Implement the FinRL-X Rebalancing Suggester

With the database populating `Effective Sentiment` dynamically, the next core phase is implementing the RL-based weight suggester.

### Action Items:
1. **RL Environment Setup (Gym/Gymnasium)**:
   * Create the environment (`suggester/env.py`) representing your portfolio.
   * **State Space**: Current weights ($w_{\text{actual}}$), current ticker cash, `Effective Sentiment` ($\text{Effective Sentiment}_{j, t}$), and portfolio drift.
   * **Action Space**: Target weight tilts ($\Delta w_t$) for portfolio constituents.
2. **Implement the Custom Reward Function ($\mathcal{R}_t$)**:
   $$\mathcal{R}_t = (R_{p, t} - R_{b, t}) - \lambda \left( \sum_{j=1}^{n} |w_{j, t} - w_{j, t-1}| \right) - \psi \cdot \mathcal{P}_{\text{slippage}}$$
   * Penalizes excessive turnover (turnover penalty coefficient $\lambda$ scaled between 5 and 15).
   * Penalizes liquidity slippage ($\psi$).
3. **Train the RL Agent**:
   * Use standard RL algorithms (such as PPO or DDPG) to train a policy that maximizes the information ratio against the baseline quarterly benchmark.
4. **Wire to IntentCore Validation Gateway**:
   * Route the output of the RL agent ($\mathbf{W}_{\text{proposed}}$) to query the IntentCore Gateway `POST /v1/validate-weights` endpoint.
   * Verify that turnover exceeding 15% gets blocked and pushed to the PM review queue.
