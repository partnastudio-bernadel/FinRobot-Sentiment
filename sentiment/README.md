# Apple (AAPL) Multi-Provider News Aggregator & Few-Shot Sentiment Agent

This repository combines a multi-provider financial news aggregator with a LangChain-powered few-shot sentiment analysis agent.

## Features

1. **Multi-Provider News Aggregation**: Consolidates, deduplicates, and standardizes news feeds from 11 different providers (OpenBB Platform + custom web/official APIs).
2. **Local Vector Database (RAG)**: Builds a local FAISS vector store from `data/financial_sentiment.csv` using NVIDIA Embeddings to act as a scoring anchor for in-context few-shot learning.
3. **Sequential Sentiment Analyzer**: Iterates through aggregated articles individually, retrieves the top 2 matching semantic calibration examples based on the article's **summary**, and prompts the LLM to score the article.
4. **Structured JSON Output**: Automatically validates and parses LLM outputs to assemble a daily report containing the overall aggregate sentiment score and warnings (e.g., mixed-sentiment detection).
5. **Separation of Concerns**: Output schemas and prompt instructions are stored in standalone files (`sentiment_schema.json` and `sentiment_prompt.txt`) for traceability.

## Project Structure

- `openbb_aapl_news.ipynb`: Jupyter Notebook containing the end-to-end pipeline.
- `sentiment_prompt.txt`: The system prompt template for the analyzer agent.
- `sentiment_schema.json`: Target output schema for sentiment reports.
- `data/`:
  - `financial_sentiment.csv`: PhraseBank dataset used to build the local vector database.
  - `news_AAPL_all.csv` and `news_AAPL_YYYY-MM-DD.json`: Output news data.
- `.env.local`: API keys configuration file (ignored from version control).
- `news_providers.md`: Summary mapping of the active OpenBB news providers.

## Run Instructions

1. Configure your `.env.local` file with the required Hugging Face and NVIDIA keys:
   ```env
   HUGGINGFACE_API_KEY = "your-hf-token"
   HUGGINGFACE_MODEL_NAME = "curiousily/Llama-3-8B-Instruct-Finance-RAG:fastest"
   HUGGINGFACE_BASE_URL = "https://router.huggingface.co/v1"

   NVIDIA_EMBEDDING_MODEL = "nvidia/nv-embed-v1"
   NVIDIA_API_ENDPOINT = "https://integrate.api.nvidia.com/v1"
   NVIDIA_API_KEY = "your-nvidia-key"
   ```
   > [!NOTE]
   > The fine-tuned model `curiousily/Llama-3-8B-Instruct-Finance-RAG:fastest` has been verified to work with the serverless **Featherless** provider hosted on Hugging Face using the Router endpoint.

2. Set up your Python environment using the local `venv`:
   ```bash
   # Activate virtual env and install requirements
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Open `openbb_aapl_news.ipynb` and execute the pipeline cells.
