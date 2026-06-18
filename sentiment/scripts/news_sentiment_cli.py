import sys
import os
import json
import argparse
from dotenv import load_dotenv

# Resolve script paths and ensure the sentiment directory is in Python's lookup path
script_dir = os.path.dirname(os.path.abspath(__file__))
sentiment_dir = os.path.dirname(script_dir)

if sentiment_dir not in sys.path:
    sys.path.insert(0, sentiment_dir)

# Import package modules
try:
    from functions.utils.news.pipeline_orchestrator import run_sentiment_analysis
except ImportError as e:
    print(f"Error importing required sentiment orchestrator: {e}", file=sys.stderr)
    print("Ensure you have activated your virtual environment and installed the dependencies.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="CLI utility for running the FinRobot Agent-to-Agent News Sentiment Analyzer."
    )
    parser.add_argument(
        "--ticker", "-t",
        type=str,
        default="AAPL",
        help="Stock ticker symbol to analyze (default: AAPL)."
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Max number of news articles to retrieve and score (default: 5)."
    )
    parser.add_argument(
        "--csv", "-c",
        type=str,
        default=None,
        help="Path to calibration CSV file (default: data/financial_sentiment.csv)."
    )
    parser.add_argument(
        "--holdings", "-k",
        type=int,
        default=5,
        help="Number of top ETF holdings to analyze if ticker is an ETF (default: 5)."
    )
    parser.add_argument(
        "--env", "-e",
        type=str,
        default=None,
        help="Path to environment file (default: .env.local)."
    )
    
    args = parser.parse_args()
    
    print(f"Starting news sentiment analysis for {args.ticker} (Limit: {args.limit}, Holdings: {args.holdings})...")
    
    try:
        report = run_sentiment_analysis(
            ticker=args.ticker,
            limit=args.limit,
            holdings=args.holdings,
            csv_path=args.csv,
            env_path=args.env
        )
        print("\n================ SENTIMENT ANALYSIS REPORT ================")
        print(json.dumps(report, indent=2))
    except Exception as e:
        print(f"\n[Error] Failed to complete analysis: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
