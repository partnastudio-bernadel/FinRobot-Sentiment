import sys

import os

from dotenv import load_dotenv



# Ensure the current directory is in the python path for importing modules

notebook_dir = os.getcwd()

if notebook_dir not in sys.path:

    sys.path.insert(0, notebook_dir)



# Load environment variables from .env.local

load_dotenv(".env.local")



import pandas as pd

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from langchain_community.vectorstores import FAISS

from langchain_core.documents import Document



# Read and clean environment variables

nvidia_embedding_model = os.getenv("NVIDIA_EMBEDDING_MODEL", "nvidia/nv-embed-v1").strip('"\' ')

nvidia_api_endpoint = os.getenv("NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1").strip('"\' ')

nvidia_api_key = os.getenv("NVIDIA_API_KEY", "").strip('"\' ')



print(f"Initializing NVIDIA Embeddings wrapper ({nvidia_embedding_model})...")

embeddings = NVIDIAEmbeddings(

    model=nvidia_embedding_model,

    nvidia_api_key=nvidia_api_key,

    base_url=nvidia_api_endpoint

)



# Load historical sentiment dataset

csv_path = "data/financial_sentiment.csv"

print(f"Loading dataset: {csv_path}...")

df_sentiment = pd.read_csv(csv_path)

df_sentiment = df_sentiment.dropna(subset=["Sentence", "Sentiment"])



# Indexing a subset of 300 rows for fast database creation and query speed

limit_rows = 300

df_subset = df_sentiment.head(limit_rows)

print(f"Indexing {len(df_subset)} records into FAISS vector database...")



documents = [

    Document(page_content=row["Sentence"], metadata={"sentiment": row["Sentiment"]})

    for _, row in df_subset.iterrows()

]



# Build local FAISS database

db = FAISS.from_documents(documents, embeddings)

print("[+] FAISS Local Vector Store created successfully!")
import json

import datetime

import autogen

from finrobot.agents.workflow import SingleAssistant

from functions.aggregator.aggregator import fetch_aggregate_all_news



ticker = "AAPL"

news_limit = 5  # Score top 5 articles



# Load prompt template and schema

with open("sentiment_prompt.txt", "r") as f:

    prompt_template = f.read()



with open("sentiment_schema.json", "r") as f:

    schema_str = f.read()



# Fetch news feed

print(f"Fetching consolidated news feed for {ticker}...")

df_news = fetch_aggregate_all_news(symbol=ticker, limit=100)



if df_news.empty:

    raise ValueError(f"No news articles found for symbol {ticker}.")



df_news_limited = df_news.head(news_limit)



# AutoGen model configuration

hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "").strip('"\' ')

hf_model_name = os.getenv("HUGGINGFACE_MODEL_NAME", "curiousily/Llama-3-8B-Instruct-Finance-RAG:fastest").strip('"\' ')

hf_base_url = os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1").strip('"\' ')



llm_config = {

    "config_list": [

        {

            "model": hf_model_name,

            "api_key": hf_api_key,

            "base_url": hf_base_url,

        }

    ],

    "temperature": 0,

}



scored_articles = []

scores = []



print(f"\nProcessing {len(df_news_limited)} articles individually...")



for idx, row in df_news_limited.iterrows():

    title = row.get('title', 'No Title')

    summary = row.get('summary', 'No Summary')

    source = row.get('source', 'Unknown Source')

    date = str(row.get('date', 'Unknown Date'))

    

    # Handle insufficient data/missing summary

    if not summary or pd.isna(summary) or len(summary.strip()) < 5:

        scored_article = {

            "title": title,

            "source": source,

            "published_at": date,

            "sentiment_label": "Neutral",

            "sentiment_score": 0.00,

            "reasoning": "Insufficient data (missing summary).",

            "flagged": True,

            "flag_reason": "Insufficient data"

        }

        scored_articles.append(scored_article)

        scores.append(0.00)

        print(f"\n[-] Article #{idx+1} Skipped (No Summary): {title[:50]}...")

        continue

        

    # Query vector store based on the article's SUMMARY

    similar_docs = db.similarity_search(summary, k=2)

    

    # Format local examples block for this summary

    examples_entry = f"Article Summary: \"{summary}\"\n"

    for i, doc in enumerate(similar_docs):

        examples_entry += f"  - Similar Sentence Example #{i+1}: \"{doc.page_content}\" -> Sentiment Label: {doc.metadata['sentiment']}\n"

        

    # Build system prompt custom to this single article

    formatted_prompt = prompt_template.format(

        SCHEMA=schema_str,

        EXAMPLES=examples_entry

    )

    

    # Configure Analyzer agent for this turn

    sentiment_agent_config = {

        "name": f"News_Sentiment_Analyzer_Turn_{idx}",

        "description": "An agent that assigns sentiment score to a single news article.",

        "profile": formatted_prompt,

        "toolkits": []

    }

    

    analyzer = SingleAssistant(

        agent_config=sentiment_agent_config,

        llm_config=llm_config,

        human_input_mode="NEVER"

)

    

    # Ask agent to score this specific article

    article_data = {

        "title": title,

        "summary": summary,

        "source": source,

        "published_at": date

    }

    

    request_msg = (

        f"Please analyze and score the following article according to the rules and schema:\n\n"

        f"{json.dumps(article_data, indent=2)}\n\n"

        "Output the JSON results and end with TERMINATE."

    )

    

    print(f"\n[+] Analyzing Article #{idx+1}: \"{title[:50]}...\"")

    analyzer.chat(request_msg)

    

    # Extract response

    last_msg = analyzer.user_proxy.last_message(analyzer.assistant)

    output_text = last_msg.get("content", "").strip()

    

    if output_text.endswith("TERMINATE"):

        output_text = output_text[:-9].strip()

        

    # Clean Markdown JSON syntax wrapper if present

    if "```json" in output_text:

        output_text = output_text.split("```json")[1].split("```")[0].strip()

    elif "```" in output_text:

        output_text = output_text.split("```")[1].split("```")[0].strip()

    try:

        parsed_output = json.loads(output_text)

        

        # Handle case where model nested output under articles list

        if isinstance(parsed_output, dict) and "articles" in parsed_output:

            article_score_data = parsed_output["articles"][0]

        else:

            article_score_data = parsed_output

            

        # Extract values with robust fallbacks

        score_val = float(article_score_data.get("sentiment_score", 0.00))

        label_val = article_score_data.get("sentiment_label", "Neutral")

        reason_val = article_score_data.get("reasoning", "")

        flagged_val = bool(article_score_data.get("flagged", False))

        flag_reason_val = article_score_data.get("flag_reason", None)

        

        scored_article = {

            "title": title,

            "source": source,

            "published_at": date,

            "sentiment_label": label_val,

            "sentiment_score": score_val,

            "reasoning": reason_val,

            "flagged": flagged_val,

            "flag_reason": flag_reason_val

        }

        

        scored_articles.append(scored_article)

        scores.append(score_val)

        print(f"    -> Score: {score_val} ({label_val})")

        

    except Exception as e:

        print(f"    -> Parse Error: {e}. Output was: {output_text[:100]}...")

        scored_articles.append({

            "title": title,

            "source": source,

            "published_at": date,

            "sentiment_label": "Neutral",

            "sentiment_score": 0.00,

            "reasoning": f"Failed to parse model response: {e}",

            "flagged": True,

            "flag_reason": "Parsing error"

        })

        scores.append(0.00)
# Compute aggregate metric

if scores:

    aggregate_score = round(sum(scores) / len(scores), 2)

else:

    aggregate_score = 0.00



if aggregate_score > 0.15:

    aggregate_label = "Positive"

elif aggregate_score < -0.15:

    aggregate_label = "Negative"

else:

    aggregate_label = "Neutral"



# Check for mixed sentiments

has_positive = any(s > 0.15 for s in scores)

has_negative = any(s < -0.15 for s in scores)

warnings = []

if has_positive and has_negative:

    warnings.append("Mixed sentiment detected across articles.")



overall_reasoning = (

    f"Analyzed {len(scored_articles)} articles for {ticker}. "

    f"The overall sentiment trend is {aggregate_label} with an average score of {aggregate_score}."

)



# Build aggregate JSON block

final_report = {

    "ticker": ticker,

    "metadata": {

        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",

        "article_count": len(scored_articles)

    },

    "articles": scored_articles,

    "aggregate_score": aggregate_score,

    "aggregate_label": aggregate_label,

    "reasoning": overall_reasoning,

    "warnings": warnings
}



print("\n================ FINAL REPORT ================")

print(json.dumps(final_report, indent=2))