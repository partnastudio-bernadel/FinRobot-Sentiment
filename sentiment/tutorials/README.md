# 🚀 Tutorials: Refactoring and Tool-Calling Evolution

This directory documents the evolutionary path of our financial sentiment analysis workflow. We transitioned a rigid, redundant, and manually-driven pipeline into a highly modular, clean, and agentic tool-driven workflow.

---

## 📂 Evolution of files

### 1. [llama3_aapl_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_aapl_news.ipynb) (Original)
The baseline implementation. It fetches, sanitizes, and scores articles inline.
* **Drawbacks**: Contains large redundant inline code blocks, duplicate file reading (for prompts and schemas), manual string-cleaning logic for agent outputs, and hardcoded RAG/embedding queries.

### 2. [llama3_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news.ipynb) (Modular Refactoring)
The first refactoring milestone. It decouples the core logic from execution cells into neat helper functions.
* **Improvements**:
  * Moved low-level tasks into helper modules (e.g., standardizing LLM configuration generation, response parsing, vector store building).
  * Introduced standard Agent Factory patterns (`create_scorer_agent` and `create_cio_agent`).
  * Packaged the data fetching, text sanitization, and FAISS vector retrieval loop into a robust `prepare_articles` function.

### 3. [llama3_news_delegation.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/tutorials/llama3_news_delegation.ipynb) (Agent-to-Agent Delegation)
The final milestone. Instead of orchestrating step-by-step sequential calls in Python orchestrator functions, we configure a direct delegation pattern where the User Proxy sends raw data directly to the **Senior Sentiment Analyst (CIO) Agent**, which automatically delegates the scoring task to the **Sentiment Scorer Agent** via an AutoGen **Nested Chat**.
* **Improvements**:
  * Employs standard AutoGen `register_nested_chats` framework to handle sub-agent division of labor.
  * Allows the CIO agent to automatically delegate context comprehension tasks to the Scorer agent.
  * Preserves clean pipeline boundaries without requiring complex LLM tool-calling capabilities.

---

## 🛠️ Underlying Codebase Enhancements

To support this evolution, the workspace files under `sentiment/` were expanded with:
* **`sentiment/functions/utils/`**:
  * [config.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/config.py): Unified LLM client configuration setups.
  * [read_and_clean.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/read_and_clean.py): System file IO readers and markdown/termination stripping utilities.
  * [build.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/build.py): FAISS database loading and embedding indexing.
* **`sentiment/functions/tools/`**:
  * [prepare_articles.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/prepare_articles.py): Contains the core `prepare_articles` function.
  * [agents.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/agents.py): Shared factory creators for Scorer and CIO agents.
  * [custom_reply.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/custom_reply.py): Custom reply function for AutoGen nested chats to enable downstream LLM execution.
* **`sentiment/prompts/`**:
  * [sentiment_prompt.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/sentiment_prompt.txt): The system prompt instructing the Sentiment Scorer agent on how to score input articles against target schema contracts.


