# Macro Ingestion - Model Testing Results

This document tracks the testing results and capabilities of various LLM models when running the Macro Ingestion and Economic Surprise calculation workflow under the new **ReAct (Reason + Action)** orchestration framework.

## Model Capability & Testing Matrix

| Model Identifier | Model Class | ReAct Trace Quality | Tool Calling Reliability | Vulnerability to Prompt Example Mimicry | Key Observations & Testing Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`minimaxai/minimax-m3`** | Small / Lightweight | Poor | Low (Bypassed tool calls) | High (Directly repeated example JSON) | Fails to trigger `get_alpha_vantage_historical_std`. Tends to copy the few-shot template placeholders. Not recommended for sub-agent tooling roles. |
| **`meta/llama-3.1-8b-instruct`** | Medium | Good | Medium | Moderate | Successfully generates reasoning traces, but requires explicit type constraints to prevent coercion errors (e.g. passing integers as strings). |
| **`mistralai/mistral-nemotron`** | Medium-Large | Excellent | High | Low | Excellent instruction following. Generates clear thoughts and matches tool signatures accurately. Good candidate for scrapers and baseline calculators. |
| **`qwen/qwen3-next-80b-a3b-instruct`** | Large | Excellent | High | Low | High reasoning capacity. Autonomous tool execution is very stable. Excels at returning raw JSON blocks without surrounding markdown prose. |
| **`meta/llama-3.1-70b-instruct`** | Large | Excellent | Very High | Low | Standard production model. Robustly handles multi-agent orchestration, complex tool inputs, type validations, and the `TERMINATE` nested chat control logic. |

---

## Key Optimization Takeaways

1. **Tool Definition Quality:** 
   Larger models (`llama-3.1-70b`, `qwen3-next`) read docstrings and argument types precisely. Smaller models require simplified, primitive types and fewer complex parameter options.
   
2. **Double Braces in String Templates:** 
   When designing prompts in Python frameworks (like AutoGen) where prompts are processed by `.format()`, all literal JSON blocks in example traces must double their braces (`{{` and `}}`) to avoid template parsing `KeyError` exceptions.

3. **Orchestration Turn Limits:** 
   Constraining nested chat limits to `max_turns: 2` ensures the sub-agents return their results in one direct interaction loop. This prevents the orchestrator's thoughts from leaking back to sub-agents and being overwritten by the summary method.

4. **Context Payload Truncation on Small Models:**
   Passing large raw payloads (e.g. 401 events, ~80 KB JSON) to smaller models (`minimax-m3`, `llama-3.1-8b`) causes silent truncation or attention loss. The agent will act as if only the first event in the list (e.g., German Retail Sales) exists. Tool wrappers must filter data at the Python/code level (`event_filter` and `currency_filter`) to return lightweight payloads (~12 events or fewer).

5. **Literalness of 70B Models vs. 8B Models:**
   * **8B Model:** Less strict. It will parse and calculate values even if they are poorly formatted or ambiguously mapped in history.
   * **70B Model:** Extremely instruction-compliant and literal. If instructions command it to extract details from "sub-agent responses in the context," but the context is injected as a message it *sent* itself (due to incorrect `recipient.send` direction), it will refuse to calculate with it. It will instead explain the scenario hypothetically using dummy variables. Correcting the AutoGen message flow to `sender.send(..., recipient=recipient)` is required to make 70B process the data as incoming input.
   * **Currency Ambiguity:** In a list of global CPI releases (CHF, USD, EUR), 70B will not guess which release is matching a generic "CPI" indicator. Clarifying the target country/currency (e.g. `"USD"`) in prompts is mandatory for precise output.

