# Running IntentCore with Live FinRobot Agents

## Complete Workflow Guide

This guide shows how to run the **complete IntentCore system** with real or simulated FinRobot agents.

---

## 🎯 Quick Start (3 Terminals)

### Terminal 1: Backend API
```bash
cd /Users/feifeige/FinRobot-IntentChain/intentcore/ui/backend
python3 -m uvicorn api:app --reload
```
✅ Running at: http://127.0.0.1:8000

### Terminal 2: Frontend UI
```bash
cd /Users/feifeige/FinRobot-IntentChain/intentcore/ui/frontend
npm run dev
```
✅ Running at: http://localhost:3000

### Terminal 3: Run Agent
```bash
cd /Users/feifeige/FinRobot-IntentChain

# Option A: Simple demo (no API keys needed)
python3 simple_agent_demo.py

# Option B: Original demo
python3 demo_intentcore.py

# Option C: Real FinRobot agent (requires API keys)
python3 run_finrobot_with_intentcore.py
```

---

## 📋 The Complete Flow

### 1. Agent Execution
The agent (FinRobot or simulated) analyzes and proposes an action:
```
Agent: "I recommend selling $75M NVDA to reduce concentration risk"
```

### 2. IntentCore Intercepts
Before the action executes, IntentCore:
- ✅ Extracts complete reasoning chain
- ✅ Validates completeness (0-100% score)
- ✅ Enforces governance policies
- ✅ Determines if human review required

### 3. Review Queue (UI)
If review required, decision appears in UI:
```
Review Queue → Shows pending decision
Click decision → See complete reasoning
```

### 4. Human Review (Portfolio Manager)
In the UI, reviewer can:
- ✅ **Approve** - Execute as proposed
- ✅ **Reject** - Block execution
- ✅ **Modify** - Change parameters (e.g., reduce amount)

### 5. Agent Continues
Based on human decision:
- **Approved** → Agent executes action
- **Rejected** → Agent stops/tries alternative
- **Modified** → Agent executes with new parameters

### 6. Audit Trail
All decisions recorded:
- Complete reasoning
- Policy checks
- Human decision
- Execution result

---

## 🧪 Testing the Flow

### Option 1: Simple Demo (Recommended)

**What it does:**
- Simulates an agent proposing a $75M NVDA trade
- Decision appears in UI Review Queue
- Waits for your approval in UI
- Shows execution result

**Run it:**
```bash
# Make sure backend and frontend are running
python3 simple_agent_demo.py
```

**In the UI:**
1. Go to http://localhost:3000
2. Click "Review Queue"
3. See the $75M NVDA trade
4. Click on it to see full reasoning
5. Make your decision (Approve/Reject/Modify)
6. See agent receive your decision in terminal

---

### Option 2: Real FinRobot Agent

**Prerequisites:**
- OpenAI API key configured in `OAI_CONFIG_LIST`
- Data source API keys in `config_api_keys`

**Run it:**
```bash
python3 run_finrobot_with_intentcore.py
```

**What happens:**
1. Real FinRobot agent analyzes NVDA position
2. Agent proposes trade based on LLM reasoning
3. IntentCore intercepts the trade
4. You review in UI
5. Agent executes based on your decision

---

## 🔧 How It Works Technically

### Agent Side (Python)

```python
from intentcore import IntentCoreRuntime, FinRobotBridge
from finrobot.agents import SingleAssistant

# 1. Initialize IntentCore
runtime = IntentCoreRuntime(db_path="intentcore.db")
bridge = FinRobotBridge(runtime=runtime, block_mode="review")

# 2. Create FinRobot agent
agent = SingleAssistant("Market_Analyst", llm_config)

# 3. Wrap agent with IntentCore
bridge.wrap_agent(agent.assistant, task="Analyze portfolio")

# 4. Run agent - high-stakes actions will be intercepted
agent.chat("Should we reduce NVDA exposure?")
```

### Review Flow

```python
# Agent proposes action
# ↓
# IntentCore intercepts
decision = runtime.process_decision(
    agent_id="agent_001",
    agent_role="Portfolio_Manager",
    task="Reduce NVDA",
    messages=[...],
    tool_call={...}
)

# ↓
# Decision written to database
runtime.db.save_reasoning_chain(chain)
runtime.db.add_to_review_queue(chain.chain_id)

# ↓
# UI polls for pending reviews
GET /api/reviews/pending
# Returns: List of decisions awaiting review

# ↓
# Human reviews in UI and submits decision
POST /api/reviews/{chain_id}/decision
{
  "reviewer_id": "sarah_chen",
  "decision": "approved",
  "rationale": "Good analysis, proceed"
}

# ↓
# Agent checks for decision
updated_chain = runtime.db.get_reasoning_chain(chain_id)
if updated_chain.human_decision == "approved":
    execute_trade()
```

---

## 📊 UI Pages Explained

### Review Queue (`/`)
- Shows all pending decisions awaiting review
- Auto-refreshes every 5 seconds
- Priority sorted (urgent → high → normal → low)

### Review Detail (`/review/{chain_id}`)
- Complete reasoning chain
- Situation, Analysis, Rationale, Risks
- Proposed action with parameters
- Policy check results
- Decision submission form

### History (`/history`)
- All past decisions
- Shows who approved/rejected
- Execution outcomes
- Searchable and filterable

### Dashboard (`/dashboard`)
- System metrics
- Total decisions, approval rate
- Average completeness score
- Daily activity trends

---

## 🎮 Interactive Demo Walkthrough

### Step 1: Start Everything
```bash
# Terminal 1
cd intentcore/ui/backend
python3 -m uvicorn api:app --reload

# Terminal 2
cd intentcore/ui/frontend
npm run dev

# Terminal 3
cd /Users/feifeige/FinRobot-IntentChain
python3 simple_agent_demo.py
```

### Step 2: Watch Terminal 3
```
Agent proposing trade: Sell $75M NVDA
Submitting to IntentCore for review...

✓ Reasoning extracted
  - Completeness: 100%
  - Governance decision: review_required

DECISION AWAITING HUMAN REVIEW
📊 Open the UI: http://localhost:3000

Waiting for your decision in the UI...
```

### Step 3: Open UI
Go to: http://localhost:3000

### Step 4: Review Queue
You'll see:
```
┌─────────────────────────────────────┐
│ HIGH PRIORITY                       │
│ Review tech portfolio concentration │
│ Portfolio_Risk_Manager              │
│ Sell $75M NVDA                      │
│ Completeness: 100%                  │
└─────────────────────────────────────┘
```

### Step 5: Click to Review
See complete reasoning:
- Situation: Tech sector at 38% (exceeds 35%)
- Analysis: $333M total tech, $280M NVDA
- Rationale: Reduce concentration + earnings risk
- Risks: Execution risk, timing risk, opportunity cost

### Step 6: Make Decision
Click "Approve" and enter rationale:
```
"Good analysis. NVDA concentration is indeed too high.
Approve $75M reduction before earnings."
```

### Step 7: Watch Terminal 3
```
DECISION RECEIVED FROM UI
Reviewer: sarah_chen
Decision: APPROVED
Rationale: Good analysis...

✅ Trade APPROVED - Agent can execute
✅ Trade executed successfully
```

### Step 8: Check History
UI → History tab:
```
Agent: Portfolio_Risk_Manager
Action: execute_trade (NVDA, SELL, $75M)
Decision: ✅ Approved by sarah_chen
Status: Completed
```

---

## 🔄 Database Connection

All three components share the same database:

```
intentcore.db (SQLite)
     ↑           ↑           ↑
     │           │           │
  Agent       Backend     Frontend
  (writes)    (reads)     (displays)
```

Location: `/Users/feifeige/FinRobot-IntentChain/intentcore.db`

---

## 🛠️ Troubleshooting

### UI shows no data
- ✅ Check backend is running: http://127.0.0.1:8000/api/metrics
- ✅ Run `simple_agent_demo.py` to create test data
- ✅ Verify database exists: `ls -lh intentcore.db`

### Agent doesn't wait for review
- ✅ Check `block_mode="review"` in bridge initialization
- ✅ Verify high-stakes function is intercepted
- ✅ Check governance policies are working

### Backend API errors
- ✅ Restart backend: Ctrl+C then `python3 -m uvicorn api:app --reload`
- ✅ Check database path is correct
- ✅ Verify all dependencies installed: `pip install fastapi uvicorn pydantic`

---

## 📝 Configuration

### Governance Policies

Edit policies in `intentcore/policies/governance.py`:

```python
"trade_limits": {
    "single_trade_max": 100_000_000,    # $100M hard limit
    "review_threshold": 50_000_000,      # Review above $50M
    "auto_approve_max": 10_000_000,      # Auto below $10M
}
```

### High-Stakes Functions

Define which functions require review:

```python
bridge.wrap_agent(
    agent,
    task="...",
    high_stakes_functions=[
        "execute_*",  # Any execute function
        "trade_*",    # Any trade function
        "sell_*",     # Sell functions
        "buy_*",      # Buy functions
    ]
)
```

---

## 🚀 Production Deployment

For production use:

1. **Database**: Migrate to PostgreSQL
   ```python
   # Use same schema, change connection string
   runtime = IntentCoreRuntime(
       db_path="postgresql://user:pass@host/intentcore"
   )
   ```

2. **API**: Add authentication
   ```python
   # Add OAuth/JWT to API endpoints
   from fastapi.security import OAuth2PasswordBearer
   ```

3. **UI**: Build and deploy
   ```bash
   cd intentcore/ui/frontend
   npm run build
   # Deploy dist/ folder to CDN/server
   ```

4. **Notifications**: Add real-time alerts
   ```python
   # Send Slack/email when review needed
   if governance.requires_review:
       send_notification(chain)
   ```

---

## ✅ Success Criteria

You know it's working when:

- ✅ Agent runs and proposes action
- ✅ Decision appears in UI Review Queue
- ✅ You can click and see full reasoning
- ✅ Your approval in UI is received by agent
- ✅ Agent executes based on your decision
- ✅ Complete history appears in UI

---

## 📚 Next Steps

1. Try `simple_agent_demo.py` first
2. Review decision in UI
3. Check History and Dashboard
4. Try real FinRobot agent with API keys
5. Customize governance policies
6. Add your own agents

---

**The system is fully functional!** 🎉

Backend + Frontend + Agent all working together.
