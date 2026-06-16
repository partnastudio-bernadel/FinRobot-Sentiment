import pandas as pd

def prepare_articles(df_news, db, limit=5, k_examples=2):
    """Format news articles and enrich them with similar calibration examples from the FAISS database.

    Triggering Criteria:
    - Must be called before initiating the chat with the Sentiment Scorer agent to package and calibrate news article texts.
    - Do not use this function if you are not processing financial news articles, or if you do not have an active FAISS database.

    Parameter Constraints:
    - df_news (pandas.DataFrame): Dataframe of fetched articles. Must contain columns: 'title' (str), 'source' (str/None), 'date' (str/datetime).
      Can contain 'summary' (str) and 'text' (str). If 'summary' is missing, it falls back to text or title.
    - db (langchain_community.vectorstores.FAISS): An initialized and populated FAISS local vector store.
    - limit (int): Slice top N articles. Range: 1 <= limit <= len(df_news). Default is 5.
    - k_examples (int): Number of semantic calibration examples to fetch from db per article. Range: k_examples >= 0. Default is 2.

    Few-Shot Examples:
    - Input:
      df_news = pd.DataFrame([{
          'title': 'Apple launches new products',
          'source': 'Reuters',
          'date': '2026-06-15',
          'summary': 'Apple unveiled new hardware products at its event.',
          'text': ''
      }])
      db = <FAISS database containing \"Tesco sales rise\" (positive)>
      
      Call: prepare_articles(df_news, db, limit=1, k_examples=1)
      
      Output:
      [
        {
          \"title\": \"Apple launches new products\",
          \"source\": \"Reuters\",
          \"published_at\": \"2026-06-15\",
          \"summary\": \"Apple unveiled new hardware products at its event.\",
          \"calibration_examples\": [
            {
              \"sentence\": \"Tesco sales rise\",
              \"sentiment\": \"positive\"
            }
          ]
        }
      ]
    """
    df_news_limited = df_news.head(limit)
    articles_to_analyze = []
    
    for idx, row in df_news_limited.iterrows():
        title = row.get('title', 'No Title')
        source = row.get('source', 'Unknown Source')
        date = str(row.get('date', 'Unknown Date'))
        summary = row.get('summary', '')
        text = row.get('text', '')
        
        # Determine fallback summary if missing
        is_summary_invalid = not summary or pd.isna(summary) or not isinstance(summary, str) or len(summary.strip()) < 5
        is_text_valid = text and not pd.isna(text) and isinstance(text, str) and len(text.strip()) >= 5
        
        if is_summary_invalid:
            summary = f"{title}\n\n{text}" if is_text_valid else title
            
        # Re-check summary validity after fallback
        if not summary or pd.isna(summary) or not isinstance(summary, str) or len(summary.strip()) < 5:
            articles_to_analyze.append({
                "title": title,
                "source": source,
                "published_at": date,
                "summary": "Insufficient data (missing summary).",
                "calibration_examples": []
            })
            continue

        # Query vector store for few-shot examples
        similar_docs = db.similarity_search(summary, k=k_examples)
        calibration_examples = [
            {"sentence": doc.page_content, "sentiment": doc.metadata["sentiment"]}
            for doc in similar_docs
        ]
        
        articles_to_analyze.append({
            "title": title,
            "source": source,
            "published_at": date,
            "summary": summary,
            "calibration_examples": calibration_examples
        })
        
    return articles_to_analyze

db_instance = None

def set_db_instance(db):
    global db_instance
    db_instance = db

def prepare_articles_tool(ticker: str, limit: int = 5) -> str:
    """Fetch recent news articles for a ticker and format them with semantic calibration examples.

    Args:
        ticker: The stock ticker symbol to analyze (e.g., 'AAPL').
        limit: The number of recent articles to score. Defaults to 5.

    Returns:
        A JSON string containing the list of formatted articles with calibration examples.
    """
    import json
    from sentiment.functions.aggregator.aggregator import fetch_aggregate_all_news
    
    if db_instance is None:
        raise ValueError("Database instance (db_instance) is not initialized. Please call set_db_instance(db) first.")
        
    df_news = fetch_aggregate_all_news(symbol=ticker, limit=100)
    
    if df_news.empty:
        raise ValueError(f"No news articles found for symbol {ticker}.")
        
    articles = prepare_articles(df_news, db_instance, limit=limit)
    return json.dumps(articles, indent=2)