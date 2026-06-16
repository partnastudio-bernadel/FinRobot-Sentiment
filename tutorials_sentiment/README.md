# 🚀 Tutorials: Refactoring and Tool-Calling Evolution

This directory documents the evolutionary path of our financial sentiment analysis workflow. We transitioned a rigid, redundant, and manually-driven pipeline into a highly modular, clean, and agentic tool-driven workflow.

---

## 📂 Evolution of files

### 1. [llama3_aapl_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/tutorials_sentiment/llama3_aapl_news.ipynb) (Original)
The baseline implementation. It fetches, sanitizes, and scores articles inline.
* **Drawbacks**: Contains large redundant inline code blocks, duplicate file reading (for prompts and schemas), manual string-cleaning logic for agent outputs, and hardcoded RAG/embedding queries.

### 2. [llama3_news.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/tutorials_sentiment/llama3_news.ipynb) (Modular Refactoring)
The first refactoring milestone. It decouples the core logic from execution cells into neat helper functions.
* **Improvements**:
  * Moved low-level tasks into helper modules (e.g., standardizing LLM configuration generation, response parsing, vector store building).
  * Introduced standard Agent Factory patterns (`create_scorer_agent` and `create_cio_agent`).
  * Packaged the data fetching, text sanitization, and FAISS vector retrieval loop into a robust `prepare_articles` function.

### 3. [llama3_news_with_tools.ipynb](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/tutorials_sentiment/llama3_news_with_tools.ipynb) (Agentic Tool Calling)
The final milestone. Instead of orchestrating data fetching and FAISS context search in local python cells, we turned this logic into a tool and gave it directly to the agent.
* **Improvements**:
  * Extracted the article preparation flow into a unified agentic tool: `prepare_articles_tool` (located in [prepare_articles.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/prepare_articles.py)).
  * The **Sentiment Scorer Agent** is now fully autonomous: it is registered with this tool and uses it to dynamically fetch current news and calibration examples on-demand.
  * Replaced the pipeline function with explicit, separate execution blocks in the notebook for easier debugging and step-by-step model testing.
  * Allows the user to dynamically customize parameters (e.g. news count limit, stock ticker) at execution time inside the chat prompt rather than hardcoding them in system settings.

---

## 🛠️ Underlying Codebase Enhancements

To support this evolution, the workspace files under `sentiment/` were expanded with:
* **`sentiment/functions/utils/`**:
  * [config.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/config.py): Unified LLM client configuration setups.
  * [read_and_clean.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/read_and_clean.py): System file IO readers and markdown/termination stripping utilities.
  * [build.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/utils/build.py): FAISS database loading and embedding indexing.
* **`sentiment/functions/tools/`**:
  * [prepare_articles.py](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/functions/tools/prepare_articles.py): Contains the core `prepare_articles` function and `prepare_articles_tool` wrapper.
* **`sentiment/prompts/`**:
  * [sentiment_prompt_with_tools.txt](file:///d:/PartnaStudio/sentinel/stack/FinRobot-IntentChain/sentiment/prompts/sentiment_prompt_with_tools.txt): The system prompt instructing the Sentiment Scorer agent on how and when to invoke the tool calling loop.
