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

## 💾 Step 2: Establish the Storage Layer (AppDB)

To connect the agent outputs to the React user interface, we must set up the **AppDB** schema contracts described in [sentiment_analyzer_architecture.md](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/sentiment_analyzer_architecture.md#L106-L111).

### Action Items:
1. **Create SQLite/Postgres Tables**:
   * **`articles`**: Tracks individual article scores, confidences, sources, and reasoning summaries.
   * **`intraday_velocity`**: Tracks ticker, hourly timestamp, and aggregate sentiment velocity.
   * **`sentiment_leaderboard`**: Compiles compound scores and 30-day percentage changes.
2. **Post-Processing Database Handler**:
   * Write a Python database connector script (`sentiment/functions/utils/db_handler.py`).
   * Hook the final JSON output of the CIO Agent (`final_report_msg`) into this script to parse, compute mathematical metrics (from Step 1), and save them immediately to the database.
3. **Trigger Ingestion on live run**:
   * Tie this handler to the FastAPI worker endpoints to make sure the React UI receives updates.

---

## 🤖 Step 3: Implement the FinRL-X Rebalancing Suggester

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
   * Verify that turnover exceeding 15% gets blocked and pushed to the React PM review queue.
